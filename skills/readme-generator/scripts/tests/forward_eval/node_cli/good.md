# csvkit

Command-line CSV filter and transformer.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Commands](#commands)
- [Development and Testing](#development-and-testing)
- [Documentation Maintenance](#documentation-maintenance)

## Installation

```bash
npm install -g csvkit
```

Requires Node.js `>=20` (from the `engines` field in `package.json`).

## Usage

```bash
csvkit --help
```

The executable is registered through the `bin` field and resolves to `src/cli.js`.

## Commands

Filtering logic lives in `src/filter.js`. Run the CLI with `--help` to list the
flags it registers — this README does not restate them, so the two cannot drift.

## Development and Testing

```bash
npm run build
npm test
npm run lint
```

> Command source: the `scripts` block in `package.json`.

Tests live in `test/filter.test.js` and run on the Node built-in test runner.

## License

MIT — see `LICENSE`.

## Documentation Maintenance

Update this README when:

- the `bin` entry or package name changes
- scripts are added to or renamed in `package.json`
- the minimum Node version in `engines` changes
