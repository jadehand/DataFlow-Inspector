import { createFeatureEngine } from "./runtime/engine.js";

// Temporary composition boundary while domain controllers own route lifecycles.
export function createApplicationController(context) {
  const cleanup = createFeatureEngine(context);
  return () => cleanup?.();
}
