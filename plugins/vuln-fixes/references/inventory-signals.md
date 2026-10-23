# Where runtime versions hide

`scan_signals.py` covers the rows marked **auto**. Rows marked **manual** need a human-style
pass with `rg`. Run `rg` with `--hidden --glob '!.git'`; most version files are dotfiles.

## All runtimes

| Location | Example | Coverage |
| --- | --- | --- |
| Dockerfile `FROM` (every stage) | `FROM node:22.20.0-alpine AS build` | auto |
| Compose, Kubernetes, CI `image:` / `container:` | `image: php:8.3-fpm` | auto |
| Digest-pinned images | `node@sha256:...` or `node:22@sha256:...` | auto (pin = digest) |
| `ARG`-parameterized images | `ARG NODE_VERSION=20` then `FROM node:${NODE_VERSION}` | manual: resolve the ARG default and any `--build-arg` in CI |
| Internal base images | `FROM registry.corp/base/node-runtime:3` | manual: find that image's own Dockerfile/repo |
| OS packages | `apt-get install nodejs`, `apk add php83` | auto (vendor-check) |
| Source builds / tarballs | `php-8.3.30.tar.xz`, `node-v22.20.0-linux-x64.tar.xz` | auto |
| Config management | Ansible `nodejs_version`, `php_version`, `gitlab_version` | auto for those keys; manual for Chef/Puppet/Salt |
| Packer, Nix, Bazel, asdf plugins | `nixpkgs.nodejs_20`, `rules_nodejs` | manual |
| Vendor appliances, Electron apps | bundled runtime | manual: flag for vendor update |

## Node.js

| Location | Example | Coverage |
| --- | --- | --- |
| `.nvmrc`, `.node-version` | `20.11.1` | auto |
| `.tool-versions`, `mise.toml`, Volta | `nodejs 22.20.0`, `"volta": {"node": ...}` | auto |
| `actions/setup-node` | `node-version: 22`, `node-version-file: .nvmrc` | auto for `node-version`; follow `node-version-file` manually |
| NodeSource repos | `deb.nodesource.com/setup_22.x` | auto (vendor-check) |
| AWS Lambda / SAM / Serverless / CDK | `runtime: nodejs20.x`, `Runtime.NODEJS_20_X` | auto (managed) |
| Cloud Functions, Azure Functions, Cloud Run buildpacks | `runtime: nodejs22`, `FUNCTIONS_WORKER_RUNTIME` + `WEBSITE_NODE_DEFAULT_VERSION` | manual |
| `package.json` `engines.node` | `>=20` | auto (signal-only) |
| Upgrade-risk signals | `assert { type: 'json' }`, `binding.gyp`, `node-gyp`, removed APIs | manual: list them for major upgrades |

## PHP

| Location | Example | Coverage |
| --- | --- | --- |
| Official and community images | `php:8.3-fpm`, `dunglas/frankenphp`, `bitnami/php-fpm` | auto |
| Distro packages | `php8.3-fpm`, `libapache2-mod-php8.1`, `php83` (Alpine), `php` (RHEL module streams) | auto (vendor-check) |
| `shivammathur/setup-php` | `php-version: '8.4'` | auto |
| `.tool-versions`, `mise.toml` | `php 8.3.30` | auto |
| Composer `require.php`, `config.platform.php` | `^8.2` | auto (signal-only) |
| PPAs and third-party repos | `ppa:ondrej/php`, `rpms.remirepo.net` | manual: check that repo's own release |
| Serverless PHP | Bref layers (`arn:aws:lambda:...:layer:php-83`) | manual: check the layer version against Bref's release notes |
| SAPI and config | `mod_php` vs FPM vs FrankenPHP; `php_value` in `.htaccess`/vhosts; `PHP_VALUE` from nginx | manual: drives exposure and mitigations |

## Self-managed GitLab

| Location | Example | Coverage |
| --- | --- | --- |
| Docker images | `gitlab/gitlab-ee:19.4.2-ee.0` | auto |
| Omnibus packages | `apt-get install gitlab-ee=19.4.2-ee.0`, `yum install gitlab-ce-19.4.2` | auto |
| Omnibus config | `gitlab.rb` (`external_url`) | auto (presence only) |
| Helm chart | `chart: gitlab/gitlab`, `version: 9.4.2`, Argo CD `targetRevision`, Terraform `helm_release` | auto; chart versions must be mapped to GitLab versions |
| GitLab Operator | `apps.gitlab.com/v1beta1` `GitLab` CR, `spec.chart.version` | auto (presence); manual for version |
| Ansible roles | `gitlab_version`, `geerlingguy.gitlab` vars | auto for `gitlab_version` |
| Not in scope | `gitlab/gitlab-runner`, GitLab.com, GitLab Dedicated | ignored by the scanner |
