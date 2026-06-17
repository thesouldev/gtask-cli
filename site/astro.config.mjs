// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import lucode from 'lucode-starlight';

// Project page on GitHub Pages: https://thesouldev.github.io/gtask-cli
export default defineConfig({
	site: 'https://thesouldev.github.io',
	base: '/gtask-cli',
	integrations: [
		starlight({
			title: 'gtask',
			description: 'Add and manage Google Tasks from the terminal.',
			customCss: ['./src/styles/custom.css'],
			favicon: '/favicon.svg',
			logo: {
				light: './src/assets/logo.svg',
				dark: './src/assets/logo-dark.svg',
			},
			// Fallbacks for browsers that do not use the SVG favicon.
			head: [
				{
					tag: 'link',
					attrs: {
						rel: 'icon',
						href: '/gtask-cli/favicon.ico',
						sizes: '32x32',
					},
				},
				{
					tag: 'link',
					attrs: {
						rel: 'apple-touch-icon',
						href: '/gtask-cli/apple-touch-icon.png',
					},
				},
			],
			social: [
				{
					icon: 'github',
					label: 'GitHub',
					href: 'https://github.com/thesouldev/gtask-cli',
				},
			],
			plugins: [
				lucode({
					navLinks: [
						{ label: 'Setup', link: '/getting-started/setup/' },
						{ label: 'CLI', link: '/reference/usage/' },
					],
				}),
			],
			sidebar: [
				{
					label: 'Start here',
					items: [{ label: 'Setup', slug: 'getting-started/setup' }],
				},
				{
					label: 'Reference',
					items: [{ label: 'CLI reference', slug: 'reference/usage' }],
				},
			],
		}),
	],
});
