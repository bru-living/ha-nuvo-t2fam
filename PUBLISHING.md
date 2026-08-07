# Publishing checklist

## GitHub repository setup

1. Push this repository root to `https://github.com/bru-living/ha-nuvo-t2fam` and make it public.
2. Set a short repository description, for example: `Home Assistant integration for one FM tuner of the NuVo NV-T2FAM`.
3. Enable GitHub Issues.
4. Add repository topics: `home-assistant`, `hacs`, `nuvo`, `nv-t2fam`, `fm-radio`, and `custom-integration`.
5. Confirm `@invalidangel23` remains the maintainer in the integration manifest.
6. Confirm the HACS and Hassfest validation workflows pass without ignored checks.

## Release

1. Ensure the version in `custom_components/nuvo_t2fam/manifest.json` matches the release version.
2. Update `CHANGELOG.md`.
3. Create and push an annotated tag such as `v1.8.1`.
4. The Release workflow creates a full GitHub release and attaches a manual-install ZIP.
5. Add the repository to HACS as a custom Integration repository and test a clean installation.

## Optional default HACS listing

Before requesting inclusion in the default HACS catalogue, submit the integration artwork to `home-assistant/brands`, publish at least one full GitHub release, and ensure the HACS and Hassfest workflows pass without ignored checks.
