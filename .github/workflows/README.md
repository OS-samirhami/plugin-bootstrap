# GitHub Actions Workflows

This directory contains automated CI/CD workflows for the plugin-bootstrap project.

## Workflows

### build.yml - Continuous Integration

**Triggers:**
- Push to `master` or `main` branches
- Pull requests to `master` or `main` branches

**What it does:**
1. Checks out the code
2. Sets up JDK 11 (Temurin distribution)
3. Validates the Gradle wrapper for security
4. Runs `./gradlew clean build check` (compiles, runs tests)
5. Builds distribution packages (`.deb` and `.rpm`)

**Purpose:** Ensures code quality and that the project builds successfully on every commit and PR.

### release.yml - Release Automation

**Triggers:**
- Push of a version tag matching pattern `v*` (e.g., `v1.2.0`)

**What it does:**
1. Checks out the code with full history
2. Sets up JDK 11 (Temurin distribution)
3. Validates the Gradle wrapper
4. Runs `./gradlew clean build` (full build with tests)
5. Builds all distribution formats:
   - Regular tar/zip archives
   - Shadow (fat) tar/zip archives
   - Debian package (`.deb`)
   - RPM package (`.rpm`)
6. Extracts version from the tag
7. Creates a GitHub release with:
   - Release name: "Release X.Y.Z"
   - All distribution packages attached
   - Auto-generated release notes from commits

**Purpose:** Automates the release process, ensuring consistent builds and making distribution packages immediately available.

## Creating a Release

To create a new release:

```bash
# 1. Update version and changelog (if needed)
# 2. Commit all changes
git add .
git commit -m "Prepare for release X.Y.Z"

# 3. Create and push the tag
git tag -a vX.Y.Z -m "Release version X.Y.Z"
git push origin main
git push origin vX.Y.Z
```

The release workflow will automatically:
- Build all packages
- Create the GitHub release
- Upload distribution files
- Make them available at: https://github.com/rundeck/plugin-bootstrap/releases

## Permissions

Both workflows require specific permissions:

- **build.yml**: Default permissions (read repository)
- **release.yml**: `contents: write` permission to create releases

These permissions are configured in each workflow file.

## Maintenance Notes

### Updating Actions

Keep actions up to date for security and features:
- `actions/checkout`: Currently v4
- `actions/setup-java`: Currently v4
- `gradle/wrapper-validation-action`: Currently v2
- `softprops/action-gh-release`: Currently v1

Check for updates: https://github.com/marketplace?type=actions

### Java Version

The project uses Java 11 as the minimum version. This is set in:
- Both workflow files
- `build.gradle` (`sourceCompatibility = 11.0`)
- Generated plugin templates

### Distribution Packages

The workflows build multiple package formats:
- **Regular distributions**: Standard tar/zip with dependencies separate
- **Shadow distributions**: Fat archives with all dependencies bundled
- **System packages**: `.deb` for Debian/Ubuntu, `.rpm` for RedHat/CentOS

Shadow distributions are recommended for most users as they're self-contained.
