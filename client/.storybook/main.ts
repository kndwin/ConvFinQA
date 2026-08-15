import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.ui.story.tsx"],
  addons: [],
  framework: "@storybook/react-vite",
};

export default config;
