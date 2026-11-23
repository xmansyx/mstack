# Lens: reuse, flow parity and quality

Does this already exist, is it how our system does it, and will the next person
be able to change it? Project conventions to read, when the project has them:
implementation entry points, types and style, and process. Each product in a
workspace has its own owners; one product's patterns apply to another only where
they actually integrate.

## Reuse

Inspect the existing owner and the closest reusable candidate for each new domain
responsibility, abstraction or likely duplicate. Search by name and by shape, and
group related symbols in one search:

```bash
git -C <path> grep -ln "CurrencySelect\|CurrencyPicker\|currencyOptions" <headSha> -- 'src/**'
git -C <path> grep -n "formatMoney\|toMinorUnits\|formatCurrency" <headSha>
```

For a new controller or service, inspect the domain owner and route registration,
not just matching names. A new abstraction needs a responsibility the closest
existing candidate cannot cover; cite both.

| Smell | Finding |
|---|---|
| New util duplicating a shared-package export | Delete it and import the shared one |
| Type redeclared locally that a shared package exports | Import it; divergence becomes a runtime bug |
| Second formatter, validator or date helper | Consolidate and name the survivor |
| New API client beside an existing one | Use the existing one or say why it cannot work |
| Copied block with small edits | Extract it, or justify the fork |
| Constant duplicating an enum value | Point at the enum |
| Component that is the existing one plus a prop | Name the prop |

For a new layer, ask whether removing it makes complexity disappear or spreads
the same rule into callers. For maintenance-facing changes, trace the next ordinary
task (such as adding a translation) and count the edits duplicated ownership causes.

## Flow parity

Find the closest flow that already works, read it end to end, and compare the
approach. For every value the new code invents, ask where the rest of the system
gets it from.

| Dimension | Ask |
|---|---|
| Data source | Does the existing flow derive this from a service or config where the new one hardcodes it? |
| Layering | Same controller → service → model split? |
| Auth and scoping | Same guard or middleware, or hand-rolled filtering? |
| Errors | Same error class, codes, shape and reporting integration? |
| Side effects | Same queue, job or engine for sends, webhooks and emails? |
| State | Same lifecycle model, or a parallel status field? |

Each violation cites the diff line and the verified prior art or an explicit rule.
Older console calls in adjacent code do not override the preferred error reporting.

## Quality

| Area | Look for |
|---|---|
| Types | Real domain shapes; external input validated and narrowed. No `any`, double casts or assertions hiding a modelling problem |
| Suppressions | No lint or type suppressions; a documented `@ts-expect-error` in a negative type test is fine |
| Comments | No TODO, FIXME, "for v2" or speculative comments |
| Dead code | Unused exports, flags and branches, checked across the whole stack |
| Deletion | The old path removed, not kept as a fallback or legacy branch |
| Simplicity | Unneeded layers, speculative configuration, duplicated sources of truth |
| Naming | The domain language of the spec and the repository |
| Components | Repeated JSX or logic that should be one shared component, especially across apps |
| Tests | Proportional coverage of changed behaviour; expectations from the requirement or an independent example, not the production calculation; realistic earlier steps for lifecycle tests; rendered evidence for visual output |
| Gate integrity | No skipped, deleted, focused or loosened tests, weaker assertions, relaxed checker settings or dropped CI jobs, unless changing that gate is the requirement |

File length alone is not a finding. Not every duplicate is wrong: two things meant
to diverge are fine, but that reasoning belongs in the PR.
