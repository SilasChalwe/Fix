# Contributing

Thank you for contributing to FIX! Please follow these guidelines to ensure your contributions align with our project architecture and release workflow.

## 1. Finding & Claiming Work

- **Roadmap & Milestones:** Check the [Roadmap (#3)](https://github.com/SilasChalwe/Fix/issues/3) for long-term direction. Only pick work from the currently **ACTIVE milestone ([Milestone Tracker #4](https://github.com/SilasChalwe/Fix/issues/4))**.
- **Claiming an Issue:** Comment on the issue before starting so maintainers and other contributors can see it is actively being worked on. Wait for assignment or acknowledgement if required.
- **Scope:** Keep one pull request focused on one issue unless dependencies or tight couplings require otherwise.

## 2. Architectural Guidelines

To maintain consistency and prevent architectural drift, adhere strictly to the rules outlined in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md):

- **Plugins by Default:** New media operations and filters must be implemented as plugins (`src/fix/plugins/`), not hardcoded into core layers.
- **Media Layering:** Shared FFmpeg/FFprobe logic and wrappers must stay within the core media layer (`src/fix/media/`).
- **Selection State:** Do not create a second selection-state system; extend or utilize existing models and core registries.
- **Private Data:** Do not commit client or private media files under any circumstances. Use synthetic fixtures or sample assets under `tests/fixtures/`.

## 3. Testing & Validation

- **Add Tests:** Always add unit or integration tests for any changed or new behavior (`tests/`).
- **Contributor Reports:** Local test reports and reproduction steps are extremely helpful in PR descriptions, but maintainer and CI validation (`.github/workflows/tests.yml`) are still strictly required before merge.

## 4. Submitting Your Pull Request

- **Reference Issues:** Reference the issue you are fixing in your pull request description (e.g., `Closes #14` or `Fixes #14`).
- **Review:** Ensure your changes do not introduce new lint or test failures.
