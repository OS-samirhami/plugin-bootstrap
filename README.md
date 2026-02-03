# Rundeck Plugin Bootstrap

[![Build Status](https://github.com/rundeck/plugin-bootstrap/actions/workflows/build.yml/badge.svg)](https://github.com/rundeck/plugin-bootstrap/actions/workflows/build.yml)

A command-line tool that generates scaffold code for Rundeck plugins, providing a fast way to start plugin development with best practices built in.

## Features

- **Multiple Plugin Types**: Generate Java, Script, or UI plugins
- **Service Type Coverage**: Support for all major Rundeck service types (Notification, WorkflowStep, ResourceModelSource, etc.)
- **Best Practices**: Generated code includes proper structure, tests, and documentation
- **Working Examples**: Ships with 14+ complete, buildable example plugins
- **Modern Stack**: Uses Groovy 3.0.21, Gradle 7.6, and current Rundeck APIs
- **Ready to Build**: Generated plugins include all necessary dependencies and build configuration

## Quick Start

### Installation

**From Release Package:**

Download the latest release from the [releases page](https://github.com/rundeck/plugin-bootstrap/releases):

```bash
# Extract the archive
tar -xzf rundeck-plugin-bootstrap-X.Y.Z.tar.gz
cd rundeck-plugin-bootstrap-X.Y.Z

# Run the tool
./bin/rundeck-plugin-bootstrap --help
```

**From Distribution Packages:**

```bash
# Debian/Ubuntu
sudo dpkg -i rundeck-plugin-bootstrap_X.Y.Z-1_all.deb
rundeck-plugin-bootstrap --help

# RedHat/CentOS
sudo rpm -i rundeck-plugin-bootstrap-X.Y.Z-1.noarch.rpm
rundeck-plugin-bootstrap --help
```

**Build From Source:**

```bash
git clone https://github.com/rundeck/plugin-bootstrap.git
cd plugin-bootstrap
./gradlew build
./run.sh --help
```

### Create Your First Plugin

```bash
# Create a notification plugin in Java
rundeck-plugin-bootstrap \
  -n "My Notification Plugin" \
  -t java \
  -s Notification \
  -d ~/my-plugins

# Build and test it
cd ~/my-plugins/my-notification-plugin
gradle build

# The plugin JAR will be in build/libs/
```

## Usage

```bash
rundeck-plugin-bootstrap [options]

Required Options:
  -n, --pluginName <name>           Name of your plugin (e.g., "My Awesome Plugin")
  -t, --pluginType <type>           Plugin type: java, script, or ui
  -s, --serviceType <service>       Rundeck service type (see list below)
  -d, --destinationDirectory <dir>  Directory where plugin will be created

Other Options:
  -h, --help                        Show help message
  -V, --version                     Show version information
```

## Plugin Types and Services

### Java Plugins (`-t java`)

Provide full access to Rundeck's API with maximum flexibility:

| Service Type (`-s`) | Description |
|---------------------|-------------|
| `Notification` | Send notifications when jobs complete, fail, or start |
| `WorkflowStep` | Add custom steps to job workflows |
| `WorkflowNodeStep` | Execute custom operations on individual nodes |
| `ResourceModelSource` | Provide dynamic node inventory from external sources |
| `LogFilter` | Process and transform job execution logs |
| `NodeExecutor` | Execute commands on nodes using custom protocols |
| `Orchestrator` | Control the order and conditions of workflow execution |
| `Option` | Generate dynamic option values for jobs |

**Example:**
```bash
rundeck-plugin-bootstrap -n "Slack Notifier" -t java -s Notification -d ./plugins
```

### Script Plugins (`-t script`)

Simpler plugins written in any scripting language:

| Service Type (`-s`) | Description |
|---------------------|-------------|
| `WorkflowNodeStep` | Script-based node step execution |
| `RemoteScriptNodeStep` | Remote script execution on nodes |
| `NodeExecutor` | Custom script-based command execution |
| `FileCopier` | Script-based file transfer to nodes |
| `NodeExecutorFileCopier` | Combined executor and file copier |
| `ResourceModelSource` | Script-based node inventory |
| `Option` | Script-based dynamic option values |

**Example:**
```bash
rundeck-plugin-bootstrap -n "Custom Node Executor" -t script -s NodeExecutor -d ./plugins
```

### UI Plugins (`-t ui`)

Extend the Rundeck web interface:

| Service Type (`-s`) | Description |
|---------------------|-------------|
| `UI` | Custom JavaScript and CSS for the Rundeck UI |

**Example:**
```bash
rundeck-plugin-bootstrap -n "Dashboard Widget" -t ui -s UI -d ./plugins
```

## Generated Plugin Structure

### Java Plugin
```
my-plugin/
├── build.gradle              # Gradle build configuration
├── README.md                 # Plugin documentation
├── src/
│   ├── main/
│   │   ├── groovy/          # Plugin source code
│   │   │   └── com/plugin/myplugin/
│   │   │       ├── MyPlugin.groovy
│   │   │       ├── Util.groovy
│   │   │       └── ExampleApis.groovy
│   │   └── resources/
│   │       └── resources/
│   │           └── icon.png  # Plugin icon
│   └── test/
│       └── groovy/
│           └── com/plugin/myplugin/
│               └── MyPluginSpec.groovy  # Spock tests
```

### Script Plugin
```
my-script-plugin/
├── build.gradle              # Build configuration
├── Makefile                  # Alternative build tool
├── plugin.yaml               # Plugin metadata
├── README.md
├── contents/
│   └── script.sh            # Your script
└── resources/
    └── icon.png
```

### Building Generated Plugins

**Java Plugins:**
```bash
cd my-plugin
gradle build
# JAR will be in build/libs/my-plugin-0.1.0.jar
```

**Script Plugins:**
```bash
cd my-script-plugin
gradle build
# Or use make
make
# ZIP will be created
```

**UI Plugins:**
```bash
cd my-ui-plugin
make
# ZIP will be created
```

### Installing in Rundeck

1. Copy the generated `.jar` or `.zip` file to Rundeck's `libext/` directory
2. Restart Rundeck (or wait for hot-reload if configured)
3. The plugin will appear in the appropriate configuration section
## Example Plugins

The `examples/` directory contains 14+ complete, working example plugins demonstrating every supported plugin type and service:

**Java Examples:**
- Notification, Workflow Step, Workflow Node Step
- Resource Model Source, Log Filter, Node Executor
- Orchestrator, Option Provider

**Script Examples:**
- Node Executor, Workflow Step, Resource Model Source
- File Copier, Option Provider

**UI Examples:**
- Basic UI Plugin with JavaScript and CSS

Each example:
- ✅ Matches exactly what the bootstrap tool generates
- ✅ Includes complete source code and tests
- ✅ Can be built and installed immediately
- ✅ Serves as a template for your own plugins
- ✅ Provides documentation references

**Explore the examples:**
```bash
ls examples/
# java-plugins/  script-plugins/  ui-plugins/
```

**Build an example:**
```bash
cd examples/java-plugins/example-notification
gradle build
# Plugin ready to install: build/libs/example-notification-0.1.0.jar
```

**Regenerate all examples:**
```bash
./generate-examples.sh
```

See [`examples/README.md`](examples/README.md) for detailed documentation of each example.

## Workflow Tips

### Rapid Plugin Development

Use this tool to accelerate plugin development with test-driven development:

1. **Generate skeleton**: Create plugin scaffold with bootstrap tool
2. **Write tests first**: Define expected behavior in Spock tests
3. **Implement features**: Write plugin code to pass tests
4. **Test locally**: Run tests with `gradle test` (fast feedback)
5. **Test in Rundeck**: Install in actual Rundeck instance

This approach is much faster than testing through the Rundeck UI during development.

**Example test-driven workflow:**
```bash
# Generate plugin
rundeck-plugin-bootstrap -n "MyPlugin" -t java -s Notification -d ./

cd my-plugin

# Write tests first (edit src/test/groovy/.../MyPluginSpec.groovy)
# Then implement features (edit src/main/groovy/.../MyPlugin.groovy)

# Run tests frequently
gradle test

# Build final plugin
gradle build
```

See this [example test suite](https://github.com/rundeck-plugins/rundeck-ec2-nodes-plugin/blob/master/src/test/groovy/com/dtolabs/rundeck/plugin/resources/ec2/EC2ResourceModelSourceSpec.groovy) for inspiration.

### Customizing Generated Plugins

After generating a plugin, you'll want to customize it:

1. **Update plugin metadata** in `build.gradle` (description, version, tags)
2. **Implement your logic** in the main plugin class
3. **Add dependencies** if needed (in `build.gradle` under `pluginLibs`)
4. **Write comprehensive tests** using Spock framework
5. **Update README.md** with usage instructions
6. **Replace icon.png** with your plugin's icon

## Development

### Building the Bootstrap Tool

```bash
# Clone the repository
git clone https://github.com/rundeck/plugin-bootstrap.git
cd plugin-bootstrap

# Build
./gradlew build

# Run locally
./run.sh --help

# Or use the built distribution
./build/distributions/rundeck-plugin-bootstrap-shadow-*/bin/rundeck-plugin-bootstrap --help
```

### Running Tests

```bash
./gradlew test
```

The test suite generates actual plugins and verifies they compile successfully.

### Creating Distribution Packages

```bash
# Create all distribution formats
./gradlew clean build buildDeb buildRpm shadowDistZip shadowDistTar

# Distributions will be in build/distributions/:
# - rundeck-plugin-bootstrap-X.Y.Z.tar
# - rundeck-plugin-bootstrap-X.Y.Z.zip
# - rundeck-plugin-bootstrap-shadow-X.Y.Z.tar
# - rundeck-plugin-bootstrap-shadow-X.Y.Z.zip
# - rundeck-plugin-bootstrap_X.Y.Z-1_all.deb
# - rundeck-plugin-bootstrap-X.Y.Z-1.noarch.rpm
```

### Creating a Release

Releases are automated via GitHub Actions when you push a version tag:

```bash
# Create and push a version tag
git tag -a v1.2.0 -m "Release version 1.2.0"
git push origin v1.2.0
```

This will automatically:
1. Build all distribution packages
2. Create a GitHub release
3. Attach all distribution files to the release
4. Generate release notes from commits

The release will be available at: `https://github.com/rundeck/plugin-bootstrap/releases`

### Project Structure

```
plugin-bootstrap/
├── src/
│   ├── main/
│   │   ├── groovy/              # Generator source code
│   │   │   └── com/rundeck/plugin/
│   │   │       ├── Generator.groovy
│   │   │       ├── generator/   # Template generators
│   │   │       ├── template/    # Core template classes
│   │   │       └── utils/       # Utilities
│   │   └── resources/
│   │       └── templates/       # Plugin templates
│   │           ├── java-plugin/
│   │           ├── script-plugin/
│   │           └── ui-script-plugin/
│   └── test/                    # Test suite
├── examples/                    # Generated example plugins
├── generate-examples.sh         # Example regeneration script
└── build.gradle                 # Build configuration
```

## Requirements

**To Run the Bootstrap Tool:**
- Java 11 or later
- No other dependencies (uses included Gradle wrapper)

**Generated Plugins Require:**
- Java 11 or later (for Java plugins)
- Gradle 7.x or later (included in generated plugins via wrapper)
- Bash or compatible shell (for Script plugins)

**Compatible with:**
- Rundeck 3.x, 4.x, and 5.x
- Groovy 3.0.21
- Spock 2.3 (for tests)

## Troubleshooting

**Issue: "Command not found" after installation**
- Ensure `/usr/bin` is in your PATH
- Check symlink: `ls -la /usr/bin/rundeck-plugin-bootstrap`

**Issue: Generated plugin doesn't appear in Rundeck**
- Verify plugin is in `libext/` directory
- Check Rundeck logs for loading errors: `service.log`
- Ensure plugin JAR/ZIP is not corrupted
- Restart Rundeck if auto-reload is disabled

**Issue: Build fails with dependency errors**
- Run `gradle build --refresh-dependencies`
- Check internet connection (Gradle needs to download dependencies)
- Verify Gradle wrapper: `./gradlew --version`

**Issue: Tests fail in generated plugin**
- This may indicate a template issue - please [report it](https://github.com/rundeck/plugin-bootstrap/issues)
- Check that you're using Java 11 or later

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run `./gradlew check` to verify
5. Submit a pull request

### Adding New Service Types

To add support for a new Rundeck service type:

1. Add the service type to `ServiceType.groovy` enum
2. Create templates in `src/main/resources/templates/`
3. Update the appropriate generator class (JavaPluginTemplateGenerator, etc.)
4. Add to the ALLOWED_TEMPLATES list
5. Create a test in the test suite
6. Update documentation

## Resources

- [Rundeck Plugin Development Guide](https://docs.rundeck.com/docs/developer/)
- [Plugin Developer Documentation](https://docs.rundeck.com/docs/developer/plugin-development.html)
- [Rundeck API Documentation](https://docs.rundeck.com/docs/api/)
- [Example Plugin Repository](https://github.com/rundeck-plugins/)

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

---

**Maintained by [Rundeck](https://www.rundeck.com/)** | **[Report Issues](https://github.com/rundeck/plugin-bootstrap/issues)** | **[View Examples](examples/)**