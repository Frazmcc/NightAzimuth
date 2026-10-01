# NightAzimuth Releases

NightAzimuth releases are now **web-first**.

The supported product is the hosted application at:

**https://nightazimuth.co.uk**

## Creating a release

Before pushing a new `v*` tag:

1. update `src/nightazimuth/__init__.py` to the matching version
2. create `docs/releases/<tag>.md`, for example `docs/releases/v1.2.0.md`
3. ensure CI and CodeQL are green
4. validate the hosted application as required
5. push the tag

The release workflow creates the GitHub release from that Markdown file.

It does **not** automatically build or attach a Windows executable.

GitHub automatically provides source archives for tagged releases.

## Historical executable releases

Older GitHub releases may contain a Windows `.exe`, user guide and checksum file. Those are retained as historical artifacts. The web application is the recommended product unless desktop support is explicitly restored in the future.

Historical release-note source files are stored under `docs/archive/releases/`.
