

import copy
import hashlib
import json
import os
from pprint import pprint

from AssetProcessor import AssetProcessor
from ChannelCache import ChannelCache
from FileFinder import FileFinder
from MongoDatabase import MongoDatabase
from helpers import get_emoji_code, pad_id


class JsonProcessor:
	def __init__(self, database: MongoDatabase, file_finder: FileFinder, json_path:str, asset_processor: AssetProcessor):
		self.json_path = json_path
		self.database = database
		self.collection_guilds = self.database.get_collection("guilds")
		self.collection_channels = self.database.get_collection("channels")
		self.collection_messages = self.database.get_collection("messages")
		self.collection_authors = self.database.get_collection("authors")
		self.collection_emojis = self.database.get_collection("emojis")
		self.collection_assets = self.database.get_collection("assets")
		self.collection_roles = self.database.get_collection("roles")
		self.collection_jsons = self.database.get_collection("jsons")
		self.file_finder = file_finder
		self.asset_processor = asset_processor

	def read_json_file(self, file_path):
		file_path_with_base_directory = self.file_finder.add_base_directory(file_path)
		with open(file_path_with_base_directory, "r", encoding='utf-8') as f:
			try:
				data = json.load(f)
			except json.decoder.JSONDecodeError:
				# probably media file too
				print("JSONDecodeError: " + file_path)
				return None

			if 'guild' not in data:  # this is not a channel export, but a downloaded media json file
				return None
		return data
	def process_guild(self, guild):
		guild["_id"] = pad_id(guild.pop("id"))
		guild["icon"] = self.asset_processor.process(guild.pop("iconUrl"))
		return guild

	def process_channel(self, channel, guild_id):
		"""
		process channel info
		does not contain messages
		"""
		channel["_id"] = pad_id(channel.pop("id"))
		channel["categoryId"] = pad_id(channel["categoryId"])
		channel["guildId"] = guild_id
		return channel

	def process_messages(self, messages, guild_id, channel_id, channel_name):
		"""
		rename id to mongo _id
		pad ids to 24 digits
		delete empty lists
		reference to guild_id and channel_id
		convert content to array
		"""
		for message in messages:
			# pad ids so they are easier to sort
			message["_id"] = pad_id(message.pop("id"))
			if "author" in message:
				message["author"]["_id"] = pad_id(message["author"].pop("id"))
				if "roles" in message["author"]:
					for role in message["author"]["roles"]:
						role["_id"] = pad_id(role.pop("id"))
			if "stickers" in message:
				for sticker in message["stickers"]:
					sticker["_id"] = pad_id(sticker.pop("id"))
			if "mentions" in message:
				for mention in message["mentions"]:
					mention["_id"] = pad_id(mention.pop("id"))
			if "reference" in message:
				message["reference"]["messageId"] = pad_id(message["reference"]["messageId"])
				message["reference"]["channelId"] = pad_id(message["reference"]["channelId"])
				message["reference"]["guildId"] = pad_id(message["reference"]["guildId"])

			if "attachments" in message:
				for attachment in message["attachments"]:
					attachment["_id"] = pad_id(attachment.pop("id"))

			# remove empty lists
			if len(message["attachments"]) == 0:
				del message["attachments"]

			if len(message["embeds"]) == 0:
				del message["embeds"]

			if len(message["mentions"]) == 0:
				del message["mentions"]

			if len(message["stickers"]) == 0:
				del message["stickers"]

			if len(message["reactions"]) == 0:
				del message["reactions"]

			# reference to guild and channel
			message["guildId"] = guild_id
			message["channelId"] = channel_id
			message["channelName"] = channel_name

			# because content may be edited, we need to change content field to an array
			latest_timestamp = message["timestampEdited"] if message["timestampEdited"] != None else message["timestamp"]
			message["content"] = [
				{
					"timestamp": latest_timestamp,
					"content": message["content"]
				}
			]


			# process assets
			if "embeds" in message:
				for embed in message["embeds"]:
					if "thumbnail" in embed:
						if "width" in embed["thumbnail"] and "height" in embed["thumbnail"]:
							original_width = embed["thumbnail"]["width"]
							original_height = embed["thumbnail"]["height"]
						embed["thumbnail"] = self.asset_processor.process(embed["thumbnail"]["url"])

						# restore some fields, because we are losing them in the asset preprocess if url is remote
						if "originalWidth" in locals():
							embed["thumbnail"]["width"] = original_width
							embed["thumbnail"]["height"] = original_height

					# embed.image field is redundant - merge with embed.images field and remove duplicate images
					# note - this field is not always duplicated with the first item in embed.images field - discordless uses only image field without creating embed.images field
					if "image" in embed:
						if "images" not in embed:  # discordless doesn't create embed.images field
							embed["images"] = []

						# merge with embed.images and remove redundant embed.image field
						embed["images"].append(embed["image"])
						del embed["image"]

					if "images" in embed:
						# deduplicate embed.images by url, unique value is image url
						unique_images = []
						for image in embed["images"]:
							if image["url"] not in [x["url"] for x in unique_images]:
								unique_images.append(image)
						embed["images"] = unique_images

						# process images
						new_images = []
						for image in embed["images"]:
							if "width" in image and "height" in image:
								original_width = image["width"]
								original_height = image["height"]
							image = self.asset_processor.process(image["url"])  # does this work?

							# restore some fields, because we are losing them in the asset preprocess if url is remote
							if "originalWidth" in locals():
								image["width"] = original_width
								image["height"] = original_height

							new_images.append(image)

						embed["images"] = new_images

					if "footer" in embed and "iconUrl" in embed["footer"]:
						embed["footer"]["icon"] = self.asset_processor.process(embed["footer"].pop("iconUrl"))

					if "author" in embed and "iconUrl" in embed["author"]:
						embed["author"]["icon"] = self.asset_processor.process(embed["author"].pop("iconUrl"))

			if "reactions" in message:
				for reaction in message["reactions"]:
					if "emoji" in reaction:
						reaction["emoji"]["guildIds"] = [guild_id]
						reaction["emoji"]["source"] = "custom"
						reaction["emoji"]["_id"] = pad_id(reaction["emoji"].pop("id"))
						if reaction["emoji"]["_id"] == pad_id(0):
							reaction["emoji"]["name"] = get_emoji_code(reaction["emoji"]["name"]).replace(":", "")
							reaction["emoji"]["_id"] = reaction["emoji"]["name"]
							reaction["emoji"]["source"] = "default"

						reaction["emoji"]["image"] = self.asset_processor.process(reaction["emoji"].pop("imageUrl"))

					if "users" in reaction:
						for user in reaction["users"]:
							user["_id"] = pad_id(user.pop("id"))
							user["avatar"] = self.asset_processor.process(user.pop("avatarUrl"))

			new_attachments = []
			if "attachments" in message:
				for attachment in message["attachments"]:
					new_attachment = self.asset_processor.process(attachment.pop("url"))

					# restore some fields, because we are losing them in the asset preprocess if url is remote
					if "fileSizeBytes" in attachment:
						new_attachment["sizeBytes"] = attachment["fileSizeBytes"]

					if "id" in attachment:
						new_attachment["id"] = attachment["_id"]

					new_attachments.append(new_attachment)

				message["attachments"] = new_attachments

			if "stickers" in message:
				for sticker in message["stickers"]:
					sticker["source"] = self.asset_processor.process(sticker.pop("sourceUrl"))

		return messages

	def process_authors(self, messages: list, guild_id: str) -> list:
		"""
		Extracts all authors from messages and returns a list of authors
		"""

		# Dictionary is used to remove duplicates
		authors = {}

		for message in messages:
			author_copy = copy.deepcopy(message["author"])
			if "author" in message:

				# process avatar in message
				author = message["author"]
				author["avatar"] = self.asset_processor.process(author.pop("avatarUrl"))
				message["author"] = author


				# extract all authors for search
				if author_copy["_id"] in authors:
					# save new nickname if different. Ignore null nicknames (discordless exports)
					if message["author"]["nickname"] not in authors[author_copy["_id"]]["nicknames"] and message["author"]["nickname"] != None:
						authors[author["_id"]]["nicknames"].append(message["author"]["nickname"])
					continue

				author_copy["guildIds"] = [guild_id]
				author_copy["avatar"] = self.asset_processor.process(author_copy.pop("avatarUrl"))
				author_copy["names"] = [author_copy.pop("name") + "#" + author_copy.pop("discriminator")]
				authors[author_copy["_id"]] = author_copy  # new author

				author_copy["nicknames"] = [author_copy.pop("nickname")]
				author_copy["nicknames"] = list(filter(None, author_copy["nicknames"]))   # remove null nicknames (discordless exports)

		# dictionary to list
		authors_list = []
		for author_id in authors:
			author_copy = authors[author_id]
			authors_list.append(author_copy)

		return authors_list

	def process_emojis(self, messages: list) -> list:
		"""
		extracts all emojis from messages and returns a list of emojis
		"""
		emojis = {}
		for message in messages:
			if "reactions" in message:
				for reaction in message["reactions"]:
					emoji = reaction["emoji"]

					if emoji["_id"] in emojis:
						# emoji already exists, ignore
						continue

					count = reaction["count"]

					emojis[emoji["_id"]] = {
						"emoji": emoji,
						"count": count
					}

		emojis_list = []
		for emoji_id in emojis:
			emojis_list.append(emojis[emoji_id])

		return emojis_list

	def process_roles(self, messages: list, guild_id: str) -> list:
		roles = {}  # role_id -> role_object

		for message in messages:
			if "author" in message:
				author = message["author"]

				if "roles" in author:
					for role in author["roles"]:
						role_id = role["_id"]

						if role_id in roles:
							# role already exists, ignore
							continue

						role["guildId"] = guild_id
						roles[role_id] = role

		return list(roles.values())

	def insert_guild(self, guild):
		database_document = self.collection_guilds.find_one({"_id": guild["_id"]})

		if database_document != None:
			# guild already exists, ignore
			return

		guild["msg_count"] = 0

		self.collection_guilds.insert_one(guild)

	def insert_channel(self, channel):
		database_document = self.collection_channels.find_one({"_id": channel["_id"]})

		if database_document != None:
			# channel already exists
			return

		channel["msg_count"] = 0

		self.collection_channels.insert_one(channel)

	def insert_author(self, author):
		database_author = self.collection_authors.find_one({"_id": author["_id"]})

		if database_author == None:
			# author doesn't exist yet
			author["msg_count"] = 0
			self.collection_authors.insert_one(author)
			return

		# merge new author with existing author
		guildIds = list(set(author["guildIds"] + database_author["guildIds"]))
		nicknames = list(set(author["nicknames"] + database_author["nicknames"]))
		names = list(set(author["names"] + database_author["names"]))

		# update guildIds and nicknames in database
		self.collection_authors.update_one({"_id": author["_id"]}, {
			"$set": {
				"guildIds": guildIds,
				"nicknames": nicknames,
				"names": names
			}
		})
		return


	def insert_emoji(self, emoji, guild_id):
		database_document = self.collection_emojis.find_one({"_id": emoji['emoji']["_id"]})

		if database_document == None:
			# new emoji
			emoji['emoji']["usage_count"] = emoji['count']
			emoji['emoji']["guildIds"] = [guild_id]
			self.collection_emojis.insert_one(emoji['emoji'])
			return

		guildIds = list(set(emoji['emoji']["guildIds"] + database_document["guildIds"]))

		# increase usage count
		self.collection_emojis.update_one({"_id": emoji['emoji']["_id"]}, {
			"$inc": {
				"usage_count": emoji['count']
			},
			"$set": {
				"guildIds": guildIds
			}
		})

	def insert_role(self, role):
		database_document = self.collection_roles.find_one({"_id": role["_id"]})

		if database_document == None:
			# new role
			self.collection_roles.insert_one(role)
			return


	def insert_message(self, message):
		"""
		Inserts a message into the database if it doesn't exist yet.
		Merges the message content with the existing message if it already exists.
		"""

		content = message["content"][0]['content']
		latest_timestamp = message["timestamp"]
		if message["timestampEdited"] != None:
			latest_timestamp = message["timestampEdited"]

		# check if message already exists. If so, get the existing message
		database_document = self.collection_messages.find_one({"_id": message["_id"]})

		if database_document != None:  # message already exists
			# print("ID exists: " + str(message["id"]))

			# if message was edited, add new content
			has_timestamp = False
			for database_document_content in database_document["content"]:
				# print(database_document_content["timestamp"] + " == " + latest_timestamp)
				if database_document_content["timestamp"] == latest_timestamp:
					has_timestamp = True
					break

			if not has_timestamp:
				database_document["content"].append({
					"timestamp": latest_timestamp,
					"content": content
				})
				# print(database_document["content"])
				# update database
				self.collection_messages.update_one({"_id": message["_id"]}, {"$set": database_document})
			return

		self.collection_messages.insert_one(message)


		# update message count of channel
		self.collection_channels.update_one({"_id": message["channelId"]}, {"$inc": {"msg_count": 1}})
		# update message count of guild
		self.collection_guilds.update_one({"_id": message["guildId"]}, {"$inc": {"msg_count": 1}})
		# update message count of author
		self.collection_authors.update_one({"_id": message["author"]["_id"]}, {"$inc": {"msg_count": 1}})
		return

	def check_if_processed(self, json_path):
		"""
		Checks if a file has already been processed
		Returns True if the file has already been processed
		Returns False if the file has not been processed yet
		"""

		json_path_with_base_dir = self.file_finder.add_base_directory(json_path)

		# read from database
		json = self.collection_jsons.find_one({"_id": json_path})

		if json == None:
			# file not found in database, it is new file
			return False

		# do quick checks first (date modified, file size), because hashing is slow

		date_modified = os.path.getmtime(json_path_with_base_dir)
		if json["date_modified"] == date_modified:
			# if time modified is the same, file was not modified
			return True

		file_size = os.path.getsize(json_path_with_base_dir)
		if json["size"] == file_size:
			# file size is the same, file was not modified
			return True

		# slow check - file hash
		file_hash = hashlib.sha256()
		with open(json_path_with_base_dir, "rb") as f:
			for byte_block in iter(lambda: f.read(4096), b""):
				file_hash.update(byte_block)
		hex_hash = file_hash.hexdigest()

		if json["sha256_hash"] == hex_hash:
			# file hash is the same, file was not modified
			return True

		# all checks failed, process the file again
		self.collection_jsons.delete_one({"_id": json_path})

	def mark_as_processed(self, json_path):
		"""
		Marks a file as processed by adding it to the jsons collection
		"""

		json_path_with_base_dir = self.file_finder.add_base_directory(json_path)

		# get file size
		file_size = os.path.getsize(json_path_with_base_dir)

		# get date modified
		date_modified = os.path.getmtime(json_path_with_base_dir)

		# get file hash of file content
		file_hash = hashlib.sha256()
		with open(json_path_with_base_dir, "rb") as f:
			for byte_block in iter(lambda: f.read(4096), b""):
				file_hash.update(byte_block)

		hex_hash = file_hash.hexdigest()

		self.collection_jsons.insert_one({
			"_id": json_path,
			"size": file_size,
			"sha256_hash": hex_hash,
			"date_modified": date_modified
		})

	def process(self):
		if self.check_if_processed(self.json_path):
			print("already processed " + self.json_path)
			return

		print("processing " + self.json_path)

		json_data = self.read_json_file(self.json_path)

		if json_data == None:
			print("invalid file " + self.json_path)
			return

		guild = self.process_guild(json_data["guild"])
		channel = self.process_channel(json_data["channel"], guild["_id"])
		messages = self.process_messages(json_data["messages"], guild["_id"], channel["_id"], channel["name"])
		authors = self.process_authors(json_data["messages"], guild["_id"])
		emojis = self.process_emojis(json_data["messages"])
		roles = self.process_roles(json_data["messages"], guild["_id"])

		# channel needs to be inserted before messages,
		# because we count the messages per channel in insert_message()
		self.insert_channel(channel)

		# authors needs to be inserted before messages,
		# because we count the messages per author in insert_message()
		for author in authors:
			self.insert_author(author)


		for message in messages:
			self.insert_message(message)

		self.insert_guild(guild)


		for emoji in emojis:
			self.insert_emoji(emoji, guild["_id"])

		for role in roles:
			self.insert_role(role)

		self.mark_as_processed(self.json_path)