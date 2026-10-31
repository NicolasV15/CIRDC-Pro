import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {themeAssets} from './themeAssets.ts';
export default defineConfig({plugins:[react(),themeAssets()],build:{outDir:'../src/cirdc/web/static',emptyOutDir:true}});
