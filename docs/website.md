# Website maintenance

The official website is published at <https://ouyangyipeng.github.io/askless/>.

## Source and build

- `web/site/index.html`: semantic page content and metadata.
- `web/site/style.css`: shared visual tokens, layout, responsive rules, reduced motion.
- `web/site/SampleExplorer.tsx`: interactive walkthrough of saved executor outputs.
- `web/site/sample.json`: eight deterministic policy outcomes from the included CSV.
- `docs/images/`: public brand artwork, actual workbench screenshot, social preview.

The website reuses the workbench's Vite, TypeScript, and React dependencies. Main content is static HTML and remains readable without JavaScript. The sample explorer uses React. There are no analytics, remote fonts, LLM calls, or credential inputs in the public page.

```bash
pnpm --dir web install --frozen-lockfile
pnpm --dir web site:dev
pnpm --dir web site:build
pnpm --dir web site:preview
```

The configured base path is `/askless/`. The build writes `docs/index.html` and `docs/assets/` without clearing documentation or images. Stable asset filenames keep obsolete build bundles from accumulating. Review and commit the generated files together with the source.

## Refresh the sample

After changing the input fixture or executor semantics:

```bash
uv run python scripts/export_site_sample.py
uv run pytest -q tests/test_site_sample.py
pnpm --dir web test
pnpm --dir web site:build
```

The test compares the stored scope, input count, and every saved branch to the current executor. Timing fields are omitted because they vary between runs.

## Publish

GitHub Pages is configured to publish from **`main` / `docs`**. The empty `docs/.nojekyll` file marks the built output as static content. A push to the publishing source triggers GitHub's managed Pages workflow. No custom workflow or deployment secrets are required.

Check the repository's Actions tab and Pages settings after publishing. Verify the public URL, image loading, all four sample policy selections, and the installation copy button. For a fork, update the repository URLs, canonical metadata, social image URL, and Vite base path before deployment.

## Design and behavior checks

Check desktop and narrow mobile layouts, keyboard focus, contrast, reduced-motion preferences, and horizontal overflow. Keep the public sample explicitly labeled as precomputed executor results. Use real workbench imagery and document the current adapter scope.

GitHub documentation: [publishing sources](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
