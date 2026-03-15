import * as OpenAPI from "fumadocs-openapi";
import { rimraf } from "rimraf";
import { openapi } from "@/lib/openapi";

const out = "./content/docs/zh/openapi";

async function generate() {
  // clean generated files
  await rimraf(out, {
    filter(v) {
      return !v.endsWith("meta.json");
    },
  });

  await OpenAPI.generateFiles({
    input: openapi,
    output: out,
    per: "operation",
    groupBy: "tag",
  });
}

void generate();
