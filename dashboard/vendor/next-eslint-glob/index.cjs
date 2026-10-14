/* eslint-disable @typescript-eslint/no-require-imports -- Next loads this adapter through CommonJS. */
"use strict";
const { isAbsolute } = require("node:path");
const { globSync } = require("tinyglobby");

// Only the API used by @next/eslint-plugin-next 16.4.0/get-root-dirs.
// Fail explicitly if a future consumer requests a different fast-glob API.
exports.globSync = (pattern, options) => {
  if (typeof pattern !== "string" || options?.onlyDirectories !== true ||
      Object.keys(options).some(key => key !== "onlyDirectories")) {
    throw new TypeError("Unsupported Next.js directory lookup; review the glob adapter");
  }
  return globSync(pattern, {
    onlyDirectories: true,
    expandDirectories: false,
    absolute: isAbsolute(pattern),
  }).map(path => path.replace(/\/$/, "") || "/");
};
