/home/jen/Documents/rtbcat-platform
├── cat-scan
│   ├── Cargo.lock
│   ├── Cargo.toml
│   ├── cat_scan
│   │   ├── Cargo.toml
│   │   ├── Dockerfile
│   │   └── src
│   ├── docker-compose.yml
│   ├── fake_bidder
│   │   ├── buildspec.yml
│   │   ├── Cargo.toml
│   │   ├── DEPLOY.md
│   │   ├── deploy.sh
│   │   ├── Dockerfile
│   │   ├── src
│   │   └── task-definition.json
│   ├── fake_ssp
│   │   ├── Cargo.toml
│   │   ├── Dockerfile
│   │   └── src
│   └── README.md
├── creative-intelligence
│   ├── analytics
│   │   ├── __init__.py
│   │   ├── mock_traffic.py
│   │   ├── __pycache__
│   │   ├── qps_optimizer.py
│   │   ├── waste_analyzer.py
│   │   └── waste_models.py
│   ├── api
│   │   ├── campaigns_router.py
│   │   ├── clustering
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── __pycache__
│   ├── collectors
│   │   ├── base.py
│   │   ├── creatives
│   │   ├── csv_reports.py
│   │   ├── __init__.py
│   │   ├── pretargeting
│   │   ├── __pycache__
│   │   └── seats.py
│   ├── config
│   │   ├── config_manager.py
│   │   ├── __init__.py
│   │   └── __pycache__
│   ├── config_performance.txt
│   ├── Dockerfile
│   ├── docs
│   │   ├── PERFORMANCE_DATA_IMPORT.md
│   │   └── performance_import_example.csv
│   ├── fraud_signals.txt
│   ├── qps_report.txt
│   ├── README.md
│   ├── requirements.txt
│   ├── scripts
│   │   ├── generate_qps_report.py
│   │   └── test_api_access.py
│   ├── size_coverage.txt
│   ├── start.sh
│   ├── storage
│   │   ├── adapters.py
│   │   ├── campaign_repository.py
│   │   ├── __init__.py
│   │   ├── migrations
│   │   ├── performance_repository.py
│   │   ├── __pycache__
│   │   ├── retention_manager.py
│   │   ├── s3_writer.py
│   │   ├── seat_repository.py
│   │   └── sqlite_store.py
│   ├── tests
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   ├── test_multi_seat.py
│   │   └── test_waste_analysis.py
│   ├── utils
│   │   ├── __pycache__
│   │   └── size_normalization.py
│   └── venv
│       ├── bin
│       ├── include
│       ├── lib
│       ├── lib64 -> lib
│       └── pyvenv.cfg
├── dashboard
│   ├── Dockerfile
│   ├── next.config.ts
│   ├── next-env.d.ts
│   ├── node_modules
│   │   ├── acorn
│   │   ├── acorn-jsx
│   │   ├── ajv
│   │   ├── @alloc
│   │   ├── ansi-regex
│   │   ├── ansi-styles
│   │   ├── anymatch
│   │   ├── any-promise
│   │   ├── arg
│   │   ├── argparse
│   │   ├── aria-query
│   │   ├── array-buffer-byte-length
│   │   ├── arraybuffer.prototype.slice
│   │   ├── array-includes
│   │   ├── array.prototype.findlast
│   │   ├── array.prototype.findlastindex
│   │   ├── array.prototype.flat
│   │   ├── array.prototype.flatmap
│   │   ├── array.prototype.tosorted
│   │   ├── ast-types-flow
│   │   ├── async-function
│   │   ├── autoprefixer
│   │   ├── available-typed-arrays
│   │   ├── axe-core
│   │   ├── axobject-query
│   │   ├── @babel
│   │   ├── balanced-match
│   │   ├── baseline-browser-mapping
│   │   ├── binary-extensions
│   │   ├── brace-expansion
│   │   ├── braces
│   │   ├── browserslist
│   │   ├── call-bind
│   │   ├── call-bind-apply-helpers
│   │   ├── call-bound
│   │   ├── callsites
│   │   ├── camelcase-css
│   │   ├── caniuse-lite
│   │   ├── chalk
│   │   ├── chokidar
│   │   ├── client-only
│   │   ├── clsx
│   │   ├── color-convert
│   │   ├── color-name
│   │   ├── commander
│   │   ├── concat-map
│   │   ├── cross-spawn
│   │   ├── cssesc
│   │   ├── csstype
│   │   ├── d3-array
│   │   ├── d3-color
│   │   ├── d3-ease
│   │   ├── d3-format
│   │   ├── d3-interpolate
│   │   ├── d3-path
│   │   ├── d3-scale
│   │   ├── d3-shape
│   │   ├── d3-time
│   │   ├── d3-time-format
│   │   ├── d3-timer
│   │   ├── damerau-levenshtein
│   │   ├── data-view-buffer
│   │   ├── data-view-byte-length
│   │   ├── data-view-byte-offset
│   │   ├── debug
│   │   ├── decimal.js-light
│   │   ├── deep-is
│   │   ├── define-data-property
│   │   ├── define-properties
│   │   ├── detect-libc
│   │   ├── didyoumean
│   │   ├── dlv
│   │   ├── doctrine
│   │   ├── dom-helpers
│   │   ├── dunder-proto
│   │   ├── eastasianwidth
│   │   ├── electron-to-chromium
│   │   ├── @emnapi
│   │   ├── emoji-regex
│   │   ├── es-abstract
│   │   ├── escalade
│   │   ├── escape-string-regexp
│   │   ├── es-define-property
│   │   ├── es-errors
│   │   ├── es-iterator-helpers
│   │   ├── @eslint
│   │   ├── eslint
│   │   ├── @eslint-community
│   │   ├── eslint-config-next
│   │   ├── eslint-import-resolver-node
│   │   ├── eslint-import-resolver-typescript
│   │   ├── eslint-module-utils
│   │   ├── eslint-plugin-import
│   │   ├── eslint-plugin-jsx-a11y
│   │   ├── eslint-plugin-react
│   │   ├── eslint-plugin-react-hooks
│   │   ├── eslint-scope
│   │   ├── eslint-visitor-keys
│   │   ├── es-object-atoms
│   │   ├── espree
│   │   ├── esquery
│   │   ├── esrecurse
│   │   ├── es-set-tostringtag
│   │   ├── es-shim-unscopables
│   │   ├── es-to-primitive
│   │   ├── estraverse
│   │   ├── esutils
│   │   ├── eventemitter3
│   │   ├── fast-deep-equal
│   │   ├── fast-equals
│   │   ├── fast-glob
│   │   ├── fast-json-stable-stringify
│   │   ├── fast-levenshtein
│   │   ├── fastq
│   │   ├── file-entry-cache
│   │   ├── fill-range
│   │   ├── find-up
│   │   ├── flat-cache
│   │   ├── flatted
│   │   ├── for-each
│   │   ├── foreground-child
│   │   ├── fraction.js
│   │   ├── fs.realpath
│   │   ├── function-bind
│   │   ├── function.prototype.name
│   │   ├── functions-have-names
│   │   ├── generator-function
│   │   ├── get-intrinsic
│   │   ├── get-proto
│   │   ├── get-symbol-description
│   │   ├── get-tsconfig
│   │   ├── glob
│   │   ├── globals
│   │   ├── globalthis
│   │   ├── glob-parent
│   │   ├── gopd
│   │   ├── graphemer
│   │   ├── has-bigints
│   │   ├── has-flag
│   │   ├── hasown
│   │   ├── has-property-descriptors
│   │   ├── has-proto
│   │   ├── has-symbols
│   │   ├── has-tostringtag
│   │   ├── @humanwhocodes
│   │   ├── ignore
│   │   ├── @img
│   │   ├── import-fresh
│   │   ├── imurmurhash
│   │   ├── inflight
│   │   ├── inherits
│   │   ├── internal-slot
│   │   ├── internmap
│   │   ├── @isaacs
│   │   ├── isarray
│   │   ├── is-array-buffer
│   │   ├── is-async-function
│   │   ├── is-bigint
│   │   ├── is-binary-path
│   │   ├── is-boolean-object
│   │   ├── is-bun-module
│   │   ├── is-callable
│   │   ├── is-core-module
│   │   ├── is-data-view
│   │   ├── is-date-object
│   │   ├── isexe
│   │   ├── is-extglob
│   │   ├── is-finalizationregistry
│   │   ├── is-fullwidth-code-point
│   │   ├── is-generator-function
│   │   ├── is-glob
│   │   ├── is-map
│   │   ├── is-negative-zero
│   │   ├── is-number
│   │   ├── is-number-object
│   │   ├── is-path-inside
│   │   ├── is-regex
│   │   ├── is-set
│   │   ├── is-shared-array-buffer
│   │   ├── is-string
│   │   ├── is-symbol
│   │   ├── is-typed-array
│   │   ├── is-weakmap
│   │   ├── is-weakref
│   │   ├── is-weakset
│   │   ├── iterator.prototype
│   │   ├── jackspeak
│   │   ├── jiti
│   │   ├── @jridgewell
│   │   ├── json5
│   │   ├── json-buffer
│   │   ├── json-schema-traverse
│   │   ├── json-stable-stringify-without-jsonify
│   │   ├── js-tokens
│   │   ├── jsx-ast-utils
│   │   ├── js-yaml
│   │   ├── keyv
│   │   ├── language-subtag-registry
│   │   ├── language-tags
│   │   ├── levn
│   │   ├── lilconfig
│   │   ├── lines-and-columns
│   │   ├── locate-path
│   │   ├── lodash
│   │   ├── lodash.merge
│   │   ├── loose-envify
│   │   ├── lru-cache
│   │   ├── lucide-react
│   │   ├── math-intrinsics
│   │   ├── merge2
│   │   ├── micromatch
│   │   ├── minimatch
│   │   ├── minimist
│   │   ├── minipass
│   │   ├── ms
│   │   ├── mz
│   │   ├── nanoid
│   │   ├── napi-postinstall
│   │   ├── @napi-rs
│   │   ├── natural-compare
│   │   ├── @next
│   │   ├── next
│   │   ├── @nodelib
│   │   ├── node-releases
│   │   ├── @nolyfill
│   │   ├── normalize-path
│   │   ├── normalize-range
│   │   ├── object-assign
│   │   ├── object.assign
│   │   ├── object.entries
│   │   ├── object.fromentries
│   │   ├── object.groupby
│   │   ├── object-hash
│   │   ├── object-inspect
│   │   ├── object-keys
│   │   ├── object.values
│   │   ├── once
│   │   ├── optionator
│   │   ├── own-keys
│   │   ├── papaparse
│   │   ├── parent-module
│   │   ├── path-exists
│   │   ├── path-is-absolute
│   │   ├── path-key
│   │   ├── path-parse
│   │   ├── path-scurry
│   │   ├── picocolors
│   │   ├── picomatch
│   │   ├── pify
│   │   ├── pirates
│   │   ├── @pkgjs
│   │   ├── p-limit
│   │   ├── p-locate
│   │   ├── possible-typed-array-names
│   │   ├── postcss
│   │   ├── postcss-import
│   │   ├── postcss-js
│   │   ├── postcss-load-config
│   │   ├── postcss-nested
│   │   ├── postcss-selector-parser
│   │   ├── postcss-value-parser
│   │   ├── prelude-ls
│   │   ├── prop-types
│   │   ├── punycode
│   │   ├── queue-microtask
│   │   ├── react
│   │   ├── react-dom
│   │   ├── react-is
│   │   ├── react-smooth
│   │   ├── react-transition-group
│   │   ├── read-cache
│   │   ├── readdirp
│   │   ├── recharts
│   │   ├── recharts-scale
│   │   ├── reflect.getprototypeof
│   │   ├── regexp.prototype.flags
│   │   ├── resolve
│   │   ├── resolve-from
│   │   ├── resolve-pkg-maps
│   │   ├── reusify
│   │   ├── rimraf
│   │   ├── @rtsao
│   │   ├── run-parallel
│   │   ├── @rushstack
│   │   ├── safe-array-concat
│   │   ├── safe-push-apply
│   │   ├── safe-regex-test
│   │   ├── scheduler
│   │   ├── semver
│   │   ├── set-function-length
│   │   ├── set-function-name
│   │   ├── set-proto
│   │   ├── sharp
│   │   ├── shebang-command
│   │   ├── shebang-regex
│   │   ├── side-channel
│   │   ├── side-channel-list
│   │   ├── side-channel-map
│   │   ├── side-channel-weakmap
│   │   ├── signal-exit
│   │   ├── source-map-js
│   │   ├── stable-hash
│   │   ├── stop-iteration-iterator
│   │   ├── string.prototype.includes
│   │   ├── string.prototype.matchall
│   │   ├── string.prototype.repeat
│   │   ├── string.prototype.trim
│   │   ├── string.prototype.trimend
│   │   ├── string.prototype.trimstart
│   │   ├── string-width
│   │   ├── string-width-cjs
│   │   ├── strip-ansi
│   │   ├── strip-ansi-cjs
│   │   ├── strip-bom
│   │   ├── strip-json-comments
│   │   ├── styled-jsx
│   │   ├── sucrase
│   │   ├── supports-color
│   │   ├── supports-preserve-symlinks-flag
│   │   ├── @swc
│   │   ├── tailwindcss
│   │   ├── tailwind-merge
│   │   ├── @tanstack
│   │   ├── text-table
│   │   ├── thenify
│   │   ├── thenify-all
│   │   ├── tinyglobby
│   │   ├── tiny-invariant
│   │   ├── to-regex-range
│   │   ├── ts-api-utils
│   │   ├── tsconfig-paths
│   │   ├── ts-interface-checker
│   │   ├── tslib
│   │   ├── @tybys
│   │   ├── type-check
│   │   ├── typed-array-buffer
│   │   ├── typed-array-byte-length
│   │   ├── typed-array-byte-offset
│   │   ├── typed-array-length
│   │   ├── type-fest
│   │   ├── @types
│   │   ├── typescript
│   │   ├── @typescript-eslint
│   │   ├── unbox-primitive
│   │   ├── undici-types
│   │   ├── @ungap
│   │   ├── @unrs
│   │   ├── unrs-resolver
│   │   ├── update-browserslist-db
│   │   ├── uri-js
│   │   ├── util-deprecate
│   │   ├── victory-vendor
│   │   ├── which
│   │   ├── which-boxed-primitive
│   │   ├── which-builtin-type
│   │   ├── which-collection
│   │   ├── which-typed-array
│   │   ├── word-wrap
│   │   ├── wrap-ansi
│   │   ├── wrap-ansi-cjs
│   │   ├── wrappy
│   │   └── yocto-queue
│   ├── package.json
│   ├── package-lock.json
│   ├── postcss.config.mjs
│   ├── public
│   │   └── cat-scanning-stats.webp
│   ├── README.md
│   ├── src
│   │   ├── app
│   │   ├── components
│   │   ├── lib
│   │   └── types
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── tsconfig.tsbuildinfo
├── docker-compose.yml
├── docs
│   ├── cat-scanning-stats.webp
│   ├── CAT_SCAN_README.md
│   ├── demo-report.html
│   ├── format_stats.csv
│   ├── index.html
│   ├── insights-screenshot.png
│   ├── phases
│   │   ├── CAT_SCAN_HANDOVER.md
│   │   ├── CHANGELOG_v6_to_v7.md
│   │   ├── CHANGELOG_v7_to_v8.md
│   │   ├── CLAUDE_CLI_Fix_Backend_Validation.md
│   │   ├── CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md
│   │   ├── CODEX_PROMPT_Fix_Backend_Validation.md
│   │   ├── CODEX_PROMPT_Forgiving_Validator.md
│   │   ├── CODEX_PROMPT_Phase8.4_LargeFileAndDBOptimization.md
│   │   ├── CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md
│   │   ├── CODEX_PROMPT_Phase9_AI_Clustering.md
│   │   ├── CODEX_PROMPT_Schema_Audit.md
│   │   ├── CSV_UPLOAD_FIX.md
│   │   ├── FIX_HOOKS_ORDER_ERROR.md
│   │   ├── handover 8.md
│   │   ├── PHASE_8.2_CODE_EXAMPLES.md
│   │   ├── PHASE_8.2_INDEX.md
│   │   ├── PHASE_8.2_PREFLIGHT.md
│   │   ├── PHASE_8.2_PROMPT.md
│   │   ├── PHASE_8.2_QUICK_REFERENCE.md
│   │   ├── PHASE_8.2_README.md
│   │   ├── PHASE_8.2_WORKFLOW.md
│   │   ├── PHASE_8.3_CODE_EXAMPLES.md
│   │   ├── PHASE_8.3_PROMPT.md
│   │   ├── PHASE_8.3_QUICK_REFERENCE.md
│   │   ├── PHASE_8.3_SUMMARY.md
│   │   ├── PHASE_8_CLI_PROMPT.md
│   │   ├── RTBcat_Handover_Platform.md
│   │   ├── RTBcat_Handover_Platform_v3.md
│   │   ├── RTBcat_Handover_Platform_v5.md
│   │   ├── RTBcat_Handover_v6.md
│   │   ├── RTBcat_Handover_v7.md
│   │   ├── RTBcat_Project_Handover.md
│   │   ├── RTBcat_QPS_Optimization_Strategy_v2.md
│   │   ├── SAVE_LOCATION_GUIDE.md
│   │   └── setup-phase-8.2-docs.sh
│   ├── report.html
│   ├── RTB_FRAUD_SIGNALS_REFERENCE.md
│   ├── segment_stats.csv
│   └── Truecaller sample ad requests.pdf
├── Edgar RTB System.md
├── infra
│   └── infra
│       └── cloudformation
├── README.md
└── tree.md

409 directories, 113 files
