# Changelog

All notable changes to the Rundeck Plugin Bootstrap project are documented in this file.

## [1.2] - 2026-02-03

### Added
- **Examples folder** with complete, working examples of all plugin types
  - 8 Java plugin examples (Notification, WorkflowStep, WorkflowNodeStep, ResourceModelSource, LogFilter, NodeExecutor, Orchestrator, Option)
  - 5 Script plugin examples (NodeExecutor, WorkflowStep, ResourceModelSource, FileCopier, Option)
  - 1 UI plugin example
- **Regeneration script** (`generate-examples.sh`) to easily recreate all examples with one command
- **Examples README** documenting the purpose and usage of each example
- **GitHub Actions** CI/CD workflow replacing Travis CI
  - Automated build and test on push/PR
  - Gradle wrapper validation
  - Artifact uploads for distribution packages
- **Better error handling** with proper exit codes and optional debug output
- **Examples .gitignore** to prevent committing build artifacts

### Changed
- **Updated Groovy** from 2.5.14 to 3.0.21 (matches current Rundeck)
- **Updated Spock** from 1.3-groovy-2.5 to 2.3-groovy-3.0
- **Updated picocli** from 4.0.0-alpha-2 to 4.7.5 (stable release)
- **Updated commons-text** from 1.4 to 1.11.0
- **Updated Gradle** wrapper from 7.2 to 7.6.4 (last stable 7.x)
- **Updated shadow plugin** from 7.1.0 to 7.1.2
- **Updated axion-release plugin** from 1.13.4 to 1.18.2
- **Updated Rundeck version** in templates from 5.0.2-20240212 to 5.7.0-20250101
- **Updated Groovy version** in templates from 3.0.9 to 3.0.21
- **Improved input validation** to preserve numbers in plugin names (e.g., "MyPlugin123" now stays as "myplugin123" instead of "myplugin")
- **Enhanced Generator.groovy** to use proper Callable<Integer> return type for exit codes
- **Bumped version** from 1.1 to 1.2
- **Updated README** with GitHub Actions badge and examples documentation

### Fixed
- **Duplicate import** in notification PluginSpec template (removed duplicate `import spock.lang.Specification`)
- **Error handling** that was swallowing stack traces - now prints to stderr with optional debug mode
- **Exit codes** - now properly returns 0 on success, 1 on failure

### Removed
- **Travis CI configuration** (`.travis.yml`) - replaced with GitHub Actions

## [1.1] - Previous Release

Initial working version with:
- Support for Java, Script, and UI plugins
- Multiple service types for each plugin type
- Template-based generation
- Basic testing

---

## Migration Notes

### From 1.1 to 1.2

1. **Groovy 3.0 Compatibility**: Generated plugins now use Groovy 3.0.21. If you have existing plugins generated with older versions, they should continue to work, but you may want to regenerate them to get the latest dependencies.

2. **Build System**: The project now uses Gradle 7.6.4. If you're building from source, your existing Gradle daemon may need to be stopped: `./gradlew --stop`

3. **CI/CD**: If you're maintaining a fork, update your CI to use GitHub Actions instead of Travis CI. The workflow file is at `.github/workflows/build.yml`.

4. **Examples**: A new `examples/` directory has been added. You can regenerate it anytime with `./generate-examples.sh`. This is especially useful for documentation purposes.

## Compatibility

- **Rundeck**: Compatible with Rundeck 3.x, 4.x, and 5.x
- **Java**: Requires Java 11 or later
- **Gradle**: Uses Gradle 7.6.4 (included via wrapper)
- **Groovy**: Generated plugins use Groovy 3.0.21

## Release Process

Releases are automated via GitHub Actions. To create a new release:

1. Update version in relevant files if needed
2. Update CHANGELOG.md with release notes
3. Commit changes
4. Create and push a version tag:
   ```bash
   git tag -a v1.2.0 -m "Release version 1.2.0"
   git push origin v1.2.0
   ```
5. GitHub Actions will automatically build and create the release with all distribution packages

The release workflow:
- Builds all distribution formats (tar, zip, deb, rpm)
- Creates a GitHub release
- Attaches distribution files
- Generates release notes from commits
