# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Added support for server-side Sessions stored in Redis ([#1]).
- Added support for HTTP compression using gzip and brotli ([#4]).
- Added support for conditional HTTP requests via `Last-Modified`
  and `ETag` headers ([#7]).
- Added support for background tasks via Celery and RedBeat ([#8]).

[#1]: https://github.com/Armonaut/Armonaut/pull/1
[#4]: https://github.com/Armonaut/Armonaut/pull/4
[#7]: https://github.com/Armonaut/Armonaut/pull/7
[#8]: https://github.com/Armonaut/Armonaut/pull/8

[Unreleased]: https://github.com/Armonaut/Armonaut/compare/5bb4827c30a3859c17f9200a454abab10cfff616...HEAD
