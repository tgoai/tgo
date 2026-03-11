/**
 * Build script: copies src/ to miniprogram_dist/ then bundles external deps
 * into each JS file using esbuild, so the published npm package is self-contained.
 *
 * Also syncs to example/node_modules/tgo-widget-miniprogram for local dev.
 */
const fs = require('fs')
const path = require('path')
const esbuild = require('esbuild')

const SRC = path.resolve(__dirname, '..', 'src')
const DIST = path.resolve(__dirname, '..', 'miniprogram_dist')

// External npm packages to bundle into miniprogram_dist
const EXTERNAL_DEPS = ['@json-render/core', 'marked', 'easyjssdk', 'zod']

function ensureDir(dir) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true })
}

function copyDir(src, dest) {
  ensureDir(dest)
  const entries = fs.readdirSync(src, { withFileTypes: true })
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name)
    const destPath = path.join(dest, entry.name)
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath)
    } else {
      fs.copyFileSync(srcPath, destPath)
    }
  }
}

// Collect all JS files in a directory
function findJS(dir, out) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  for (const e of entries) {
    const full = path.join(dir, e.name)
    if (e.isDirectory()) findJS(full, out)
    else if (e.name.endsWith('.js')) out.push(full)
  }
}

// Check if a JS file requires any external dep
function hasExternalDep(filePath) {
  const code = fs.readFileSync(filePath, 'utf8')
  return EXTERNAL_DEPS.some(dep => code.includes(`require('${dep}')`) || code.includes(`require("${dep}")`))
}

async function main() {
  // 1. Clean & copy src -> miniprogram_dist
  if (fs.existsSync(DIST)) {
    fs.rmSync(DIST, { recursive: true, force: true })
  }
  copyDir(SRC, DIST)
  console.log(`[build] Copied ${SRC} -> ${DIST}`)

  // 2. Bundle external deps into JS files using esbuild
  const allJS = []
  findJS(DIST, allJS)
  const toBuild = allJS.filter(hasExternalDep)

  if (toBuild.length > 0) {
    // Build a regex to match internal relative requires — these stay external
    const relativeFilter = /^\.\.?\//

    for (const file of toBuild) {
      await esbuild.build({
        entryPoints: [file],
        bundle: true,
        format: 'cjs',
        target: 'es2020',
        platform: 'neutral',
        outfile: file,
        allowOverwrite: true,
        // Keep relative requires (internal modules) as external
        plugins: [{
          name: 'externalize-relative',
          setup(build) {
            build.onResolve({ filter: /.*/ }, args => {
              if (args.kind === 'entry-point') return
              // Only externalize relative paths resolved from miniprogram_dist files
              // (not from node_modules — those are internal to the bundled dep)
              if (relativeFilter.test(args.path) && args.resolveDir.startsWith(DIST)) {
                return { path: args.path, external: true }
              }
            })
          }
        }]
      })
    }
    console.log(`[build] Bundled external deps into ${toBuild.length} files`)
  }

  // 3. Sync to example/node_modules/tgo-widget-miniprogram
  const EXAMPLE_NODE_MOD = path.resolve(__dirname, '..', 'example', 'node_modules', 'tgo-widget-miniprogram')
  if (fs.existsSync(path.resolve(__dirname, '..', 'example', 'node_modules'))) {
    // Remove symlink or old copy
    try {
      if (fs.lstatSync(EXAMPLE_NODE_MOD).isSymbolicLink()) {
        fs.unlinkSync(EXAMPLE_NODE_MOD)
      } else if (fs.existsSync(EXAMPLE_NODE_MOD)) {
        fs.rmSync(EXAMPLE_NODE_MOD, { recursive: true, force: true })
      }
    } catch (e) {}
    ensureDir(EXAMPLE_NODE_MOD)
    const EXAMPLE_MP_DIST = path.join(EXAMPLE_NODE_MOD, 'miniprogram_dist')
    copyDir(DIST, EXAMPLE_MP_DIST)
    const pkgSrc = path.resolve(__dirname, '..', 'package.json')
    fs.copyFileSync(pkgSrc, path.join(EXAMPLE_NODE_MOD, 'package.json'))
    console.log(`[build] Synced to ${EXAMPLE_NODE_MOD}`)
  }
}

main().catch(err => {
  console.error('[build] Failed:', err)
  process.exit(1)
})
