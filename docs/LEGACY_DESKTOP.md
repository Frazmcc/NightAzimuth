# Legacy Windows Desktop Build

NightAzimuth originally shipped as a local Windows/Tkinter application packaged with PyInstaller.

That desktop application is now **legacy/historical**.

## Recommended product

Use the hosted web application:

**https://nightazimuth.co.uk**

The web version has moved beyond the released executable in UI, hosted data access, aircraft sharing/resilience, performance work and validated multi-user scalability.

## Existing GitHub EXE releases

Existing `.exe` files are retained as historical artifacts so the project history remains reproducible. They should not be interpreted as the best or current NightAzimuth experience.

They may lack later web-only behaviour, fixes and scalability work.

## Future releases

New release tags should not automatically publish a Windows executable.

The repository release workflow is web-first: release notes describe the deployed product and GitHub supplies source archives automatically.

A Windows binary should only return as a normal release asset if there is an explicit future decision to bring the desktop client back to feature parity and maintain it as a supported product.

## Source code

Desktop code and `build_windows.ps1` remain in the repository for:

- historical reference
- experimentation
- potential future desktop work
- detecting accidental breakage while legacy packaging checks are retained

They are not the primary deployment path.

## Support expectation

Bug reports should normally be reproduced against the hosted web application first.

Desktop-only issues may be accepted as historical/legacy issues, but they should not block web releases unless the desktop client is deliberately returned to supported status.
