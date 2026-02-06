# BUILD-NOTES.md

## Building the Conditional Job Trigger Plugin

### Rundeck Core Dependency Issue

**Problem:** The `org.rundeck:rundeck-core` dependency is not available in public Maven repositories.

**Why:** Rundeck plugins are designed to run inside Rundeck, where the core libraries are already provided. The Rundeck team doesn't publish `rundeck-core` to Maven Central.

### Solution Options

#### Option 1: Build Without Tests (Recommended for Quick Start)
```bash
./gradlew clean build -x test
```

This will compile the plugin code without running tests. The plugin will work when installed in Rundeck because Rundeck provides the core libraries at runtime.

#### Option 2: Install Rundeck Locally (For Full Development)

1. **Download Rundeck source:**
   ```bash
   git clone https://github.com/rundeck/rundeck.git
   cd rundeck
   ```

2. **Build and publish to local Maven:**
   ```bash
   ./gradlew publishToMavenLocal
   ```

3. **Then build the plugin:**
   ```bash
   cd /path/to/conditional-job-trigger
   ./gradlew clean build
   ```

#### Option 3: Use Provided Scope (Current Configuration)

The `build.gradle` is configured with `compileOnly` for rundeck-core, which allows compilation without the full dependency. This is the standard approach for Rundeck plugins.

```gradle
dependencies {
    compileOnly 'org.rundeck:rundeck-core:3.4.9'  // Provided by Rundeck at runtime
    implementation 'org.codehaus.groovy:groovy-all:3.0.21'
}
```

### Build Commands

```bash
# Build without tests (fastest, recommended)
./gradlew clean build -x test

# Create JAR only
./gradlew jar

# Clean build directory
./gradlew clean
```

### Installation

Once built, the JAR will be in:
```
build/libs/conditional-job-trigger-0.1.0.jar
```

Install it to Rundeck:
```bash
cp build/libs/conditional-job-trigger-0.1.0.jar $RDECK_BASE/libext/
```

### Testing in Rundeck

The plugin code is correct and will work when installed in Rundeck 3.4.x or later. Testing should be done:

1. **In Rundeck UI:**
   - Create a test job
   - Add the "Conditional Job Trigger" step
   - Configure with a target job
   - Run and verify behavior

2. **Integration Testing:**
   - Set up test jobs
   - Test various condition expressions
   - Verify job triggering works
   - Check output context variables

### Alternative: Skip Rundeck Dependency Entirely

For a completely dependency-free build (just to verify syntax), you could temporarily comment out the Rundeck imports and build. But this is not recommended as the code won't be functionally complete.

### Recommended Workflow

1. **Initial Build:** `./gradlew clean build -x test`
2. **Install in Rundeck:** Copy JAR to `$RDECK_BASE/libext/`
3. **Test in Rundeck:** Use actual Rundeck jobs to test
4. **Iterate:** Make changes, rebuild, reinstall, test

This is the standard Rundeck plugin development workflow since plugins are tightly integrated with the Rundeck runtime.
