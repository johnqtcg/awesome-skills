# {CLI_NAME}

![CI](https://github.com/acme/csvkit/actions/workflows/ci.yml/badge.svg)
![Downloads](https://img.shields.io/npm/dm/csvkit)

## Table of Contents

- [Setup](#installation)
- [Usage](#usage)
- [Release Process](#release-process)

## Installation

```bash
npm install -g csvkit
```

## Usage / 用法

```bash
csvkit filter --where "age > 30" data.csv
```

Parsing lives in `src/parser/index.js`.

## Release Process

```bash
npm run release
npm run publish:latest
```
