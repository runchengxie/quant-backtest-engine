import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import type { LearningTrace } from "./trace-schema";
import { isLearningTrace } from "./trace-schema";
const root = pathToFileURL(resolve(process.cwd(), "../docs") + "/");
function read(path: string) {
  return readFileSync(new URL(path, root));
}
const raw = read("assets/learning/manifest.json");
export const manifest = JSON.parse(raw.toString());
export const manifestHash = createHash("sha256").update(raw).digest("hex");
export const english = JSON.parse(
  read("assets/method/en.json").toString(),
) as Record<string, string>;
export function catalog(locale: string): Record<string, string> {
  return {
    ...english,
    ...JSON.parse(read("assets/method/" + locale + ".json").toString()),
  };
}
export function traces(scene: string): LearningTrace[] {
  return manifest.traces
    .filter((t: any) => t.scene_id === scene)
    .map((t: any) => {
      const raw = read(t.url);
      if (createHash("sha256").update(raw).digest("hex") !== t.sha256)
        throw new Error("trace byte mismatch");
      const value = JSON.parse(raw.toString());
      if (!isLearningTrace(value)) throw new Error("invalid learning trace");
      return value;
    });
}
export function flatten(value: unknown, path = ""): Array<[string, unknown]> {
  if (value !== null && typeof value === "object")
    return Object.entries(value).flatMap(([key, v]) =>
      flatten(v, path + "/" + key),
    );
  return [[path, value]];
}
export function display(value: unknown, c: Record<string, string>) {
  return value === null
    ? c["value.unknown"]
    : typeof value === "boolean"
      ? c["value." + value]
      : String(value);
}
