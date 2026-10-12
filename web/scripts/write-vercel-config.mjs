import { writeFileSync } from "node:fs";

for (const key of ["VERCEL_ORG_ID", "VERCEL_PROJECT_ID", "VERCEL_TOKEN"]) {
  if (!process.env[key]) {
    throw new Error(`Missing GitHub Actions secret: ${key}.`);
  }
}

const rawOrigin = process.env.API_ORIGIN;
if (!rawOrigin) {
  throw new Error("Set API_ORIGIN to the HTTPS origin of the deployed API.");
}

const apiOrigin = new URL(rawOrigin);
if (
  apiOrigin.protocol !== "https:" ||
  apiOrigin.pathname !== "/" ||
  apiOrigin.search ||
  apiOrigin.hash
) {
  throw new Error("API_ORIGIN must be an HTTPS origin with no path, query, or fragment.");
}

const config = {
  $schema: "https://openapi.vercel.sh/vercel.json",
  rewrites: [
    { source: "/api/:path*", destination: `${apiOrigin.origin}/:path*` },
    { source: "/(.*)", destination: "/index.html" },
  ],
};

writeFileSync("vercel.json", `${JSON.stringify(config, null, 2)}\n`);
