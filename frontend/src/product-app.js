import { createApplicationController } from "./pages/application-controller.js";

export function initProductApp(context) {
  return createApplicationController(context);
}
