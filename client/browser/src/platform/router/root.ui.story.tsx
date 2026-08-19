import type { Meta, StoryObj } from "@storybook/react-vite";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { RootLayout } from "./root.ui";

const rootRoute = createRootRoute({ component: RootLayout });
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: () => <div className="p-8">Route content rendered through the root outlet.</div>,
});
const router = createRouter({
  routeTree: rootRoute.addChildren([indexRoute]),
  history: createMemoryHistory({ initialEntries: ["/"] }),
});

const meta = {
  title: "Platform/Router/Root Layout",
  component: RootLayout,
  render: () => <RouterProvider router={router} />,
} satisfies Meta<typeof RootLayout>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};
