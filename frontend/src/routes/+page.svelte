<!-- WELCOME PAGE -->

<script>
	import Container from "../components/containers/Container.svelte";
	import { settingsShown } from "src/components/settings/settingsStore";
</script>


<div class="container">
	<Container>
		<img src="/logo.png" alt="Logo d'Epsius">
		<h1>Bienvenue dans les archives d'Epsius</h1>
		<p>
			Vous pouvez consulter les archives des salons temporaires qui ne sont plus disponible sur Discord.
			<br>Les archives sont rangées par année et commencent par l'année 2022-2023.
		</p>
		<p>Ce site se base sur le projet <a href="https://github.com/slatinsky/DiscordChatExporter-frontend" target="_blank" rel="noreferrer noopener">slatinsky/DiscordChatExporter-frontend</a> et récupère les salons grâce à <a href="https://github.com/Tyrrrz/DiscordChatExporter" target="_blank" rel="noreferrer noopener">Tyrrrz/DiscordChatExporter</a>.</p>
		<div class="settings" on:click={()=>$settingsShown = true}>
			<svg aria-hidden="true" role="img" width="20" height="20" viewBox="0 0 24 24"><path fill="currentColor" fill-rule="evenodd" clip-rule="evenodd" d="M19.738 10H22V14H19.739C19.498 14.931 19.1 15.798 18.565 16.564L20 18L18 20L16.565 18.564C15.797 19.099 14.932 19.498 14 19.738V22H10V19.738C9.069 19.498 8.203 19.099 7.436 18.564L6 20L4 18L5.436 16.564C4.901 15.799 4.502 14.932 4.262 14H2V10H4.262C4.502 9.068 4.9 8.202 5.436 7.436L4 6L6 4L7.436 5.436C8.202 4.9 9.068 4.502 10 4.262V2H14V4.261C14.932 4.502 15.797 4.9 16.565 5.435L18 3.999L20 5.999L18.564 7.436C19.099 8.202 19.498 9.069 19.738 10ZM12 16C14.2091 16 16 14.2091 16 12C16 9.79086 14.2091 8 12 8C9.79086 8 8 9.79086 8 12C8 14.2091 9.79086 16 12 16Z"></path></svg>
			Settings
		</div>
	</Container>
</div>

<style>

	.container {
		height: calc(100dvh - 16px);
	}
	img {
		width: 100px;
		height: 100px;
	}

	.settings {
		display: flex;
		align-items: center;
		gap: 5px;
		padding: 10px 10px 10px 0;
		cursor: pointer;
	}
</style>