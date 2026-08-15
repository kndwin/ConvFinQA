import type { Preview } from "@storybook/react-vite";
import "../src/platform/style/global.css";

const preview: Preview = {
  parameters: {
    layout: "fullscreen",
  },
};

export default preview;
