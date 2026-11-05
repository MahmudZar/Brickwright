# CSS Rules

Read this when writing or reviewing CSS for a Brickwright mockup, a Bricks global class, a shortcode's markup or any override. It is the standard the Brickwright library checks and the one a reference store was built with (53 stylesheets, 23,000 lines, 98% logical properties, zero BEM violations).

These are defaults. A project's own CSS standard always wins; use this where there is none.

Built for **Bricks Builder + TwoKit**. Every rule here assumes the CSS ends up as Bricks **global classes with custom CSS only**.

## Non-Negotiable Rules

| Rule | Why |
| --- | --- |
| Vanilla CSS only. No preprocessors, no utility frameworks beyond TwoKit's own utility classes. | The CSS is pasted into Bricks as written. |
| One global class per BEM block or element. | Each class becomes one Bricks global class. |
| Every rule starts with the class that owns it. | The library routes each rule to its first class. A rule no class owns fails the build. |
| States, children, `@media` and `@container` live **inside** the owning class (native nesting). | Bricks prints a class's CSS only when the class is on the page. |
| Logical properties, always. | Works in any writing direction, and matches the rest of the codebase. |
| TwoKit variables for anything systemic. | One change in TwoKit updates the whole site. |
| No CSS on elements (`_cssCustom` on an element), nothing in Bricks' Style panel. | One source of truth: the class. The library refuses element CSS. |

## TwoKit First

Use the token before writing a value. Never redefine a value TwoKit already has.

| Need | Use |
| --- | --- |
| Space between things | `--space-4xs` to `--space-4xl` |
| Section padding, gutters, widths | `--sctn-block-padding`, `--sctn-inline-padding`, `--site-gutter`, `--content-width` (`-xs` to `-xl`) |
| Type sizes | `--text-xs` to `--text-4xl`, headings `--h1` to `--h4`, `--text-line-height` |
| Fonts | `--font-body`, `--font-heading` |
| Text colour | `--text-primary`, `--text-secondary`, `--text-muted`, `--text-disabled` |
| Surfaces and borders | `--surface-*` (page, card, raised, popover, dialog), `--border`, `--border-subtle`, `--border-strong` |
| Brand and status colours | `--primary-50` to `--primary-950`, `--success-*`, `--warning-*`, `--error-*`, `--info-*` |
| Radius, shadow | `--radius-xs` to `--radius-xxl`, `--radius-circle`; `--shadow-card`, `--shadow-raised`, `--shadow-popover`, `--shadow-dialog` |
| Buttons | `--btn-*` (padding, font size, radius, per-variant colours) |
| Motion | `--transition`, `--transition-duration`, `--transition-timing` |
| Grids | `--grid-1` to `--grid-12`, `--grid-auto-*` |
| Colours that must not flip with the theme | `--light-*` / `--dark-*` |

- **Tints:** mix from tokens, don't invent colours: `color-mix(in oklab, var(--primary-500) 12%, transparent)`.
- **Dark sections:** put TwoKit's `theme-dark` class on the section. Tokens and components flip by themselves. Don't hand-pick `--dark-*` colours.
- **Raw values are allowed only for:** one-off geometry (aspect ratios, an illustration, an icon box), hairlines up to 2px, and brand colours that aren't ours (card networks, social logos). Everything else uses a token. If no token fits, use the nearest one rather than a new raw value.
- **Repeated raw values become a custom property.** If the same `rgba(255 255 255 / 62%)` highlight appears in two classes, it belongs in one variable.

## BEM

- `block`, `block__element`, `block--modifier`. Lowercase, hyphens inside words: `product-card__price-row`.
- Element names describe the role, not the look: `card__title`, not `card__bold-text`.
- One level of elements only. `card__media__img` is wrong; it's `card__img`.
- A block inside another block keeps its own name. Don't rename it `parent__child-block`.
- **Write every element as its own top-level rule.** Native CSS nesting has no `&__title` (that is Sass). Inside Bricks each element is a separate global class anyway.

```css
/* right */
.card { display: grid; gap: var(--space-s); }
.card__title { font-size: var(--h4); }

/* wrong: invalid in native CSS, and two classes in one */
.card {
  &__title { font-size: var(--h4); }
}
```

## Modifiers or Data Attributes

| Use a modifier class (`card--featured`) when | Use a data attribute (`[data-tint="mint"]`) when |
| --- | --- |
| A designer picks the variant in the builder | The value comes from content: an ACF field, a loop, a dynamic tag (`data-tint="{acf_tint}"`) |
| It's one of a few fixed looks | JavaScript sets it as state (`data-state="open"`, `data-step="2"`) |
| | A component property drives it (`data-btn-size="l"`) |

- Scope attribute selectors to their block: `.policy-card[data-tint="mint"]`, never a bare `[data-tint="mint"]`.
- Only style attribute values the markup actually sets.
- A modifier still needs its own global class in Bricks, even when its CSS lives inside the base class.

## Nesting

- Nest states, pseudo-elements, children inside the block, `@media` and `@container` under the class that owns them.
- Start nested selectors with `&`: `& > .card__img`, `&:hover`, `&::before`, `&[data-state="open"]`.
- Maximum three levels deep. Flatten anything deeper.
- `:has()` can't contain another `:has()`. Rewrite with one `:has()`: `table:not(:has(select:not(.x)))`.

## Logical Properties

| Physical | Logical |
| --- | --- |
| `width` / `height` | `inline-size` / `block-size` |
| `min-width`, `max-height` | `min-inline-size`, `max-block-size` |
| `margin-top` / `margin-bottom` | `margin-block-start` / `margin-block-end` (or `margin-block`) |
| `padding-left` / `padding-right` | `padding-inline-start` / `padding-inline-end` (or `padding-inline`) |
| `top`, `right`, `bottom`, `left` | `inset-block-start`, `inset-inline-end`, ... or `inset` |
| `border-left` | `border-inline-start` |
| `text-align: left` | `text-align: start` |

Exceptions: `overflow-x` / `overflow-y` (the logical versions still lack support), and undoing a third party's physical rule.

## Container Queries First

Ask where the layout decision belongs:

- **The component's own space decides** (a card in a 1, 2 or 4 column grid, a product row, a featured card that sits in a sidebar or full width): use a **container query**.
- **The whole page or the user decides** (page columns, the nav breakpoint, `prefers-reduced-motion`, `hover`, `pointer`): use a **media query**.

```css
.product-row {
  container: product-row / inline-size;
}
.product-row__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  @container product-row (width >= 40rem) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}
```

- **Name every container** (`container: name / inline-size`) and query it by name.
- Container query sizes are in **rem** (`@container shop-main (width >= 44rem)`): they follow the content and the text size. Media queries stay in px to match Bricks' breakpoints.
- **Never put `container-type` on a CSS grid or on a grid item.** Chrome then sizes the grid rows wrong (extra space, or the last item cut off). Put it on a plain wrapper or the section container above the grid.
- Scale illustrations with container units through a registered property, not a bare `cqi`, which changes meaning inside nested containers:

```css
@property --x-u { syntax: "<length>"; inherits: true; initial-value: 0px; }
.scene { container-type: inline-size; }
.scene__art { --x-u: calc(100cqi / 100); }
```

## Media Queries

- **Range syntax and px:** `@media (width >= 992px)`, `@media (width < 768px)`. Never `min-width` / `max-width`, never `991.98px` tricks.
- **Breakpoints = the site's Bricks breakpoints.** Use the same few numbers everywhere (reference store: `640`, `768`, `992`, `1200`, menu `1030`). Never the same breakpoint in two units.
- Mobile first: base styles for phones, then `width >=` steps up.
- Hover effects only for real mice: `@media (hover: hover) and (pointer: fine)`.
- Every animation or large transition gets a `@media (prefers-reduced-motion: reduce)` branch that stops it.

## Units

| For | Use |
| --- | --- |
| Type and spacing | TwoKit tokens (rem underneath) |
| Readable line length | `ch` (`max-inline-size: 65ch`) |
| Layout | `%`, `fr`, `minmax()`, `min()`, `max()`, `clamp()` |
| Full-height areas | `dvh` / `svh` / `lvh`, never `vh` (mobile toolbars break it) |
| Borders, hairlines | px |
| Media queries | px |

- Sibling spacing comes from `gap` on the flex or grid parent, not margins on the children.
- Give flexible children `min-inline-size: 0` so long words can't burst the layout.

## Modern CSS We Use

| Feature | Use it for |
| --- | --- |
| `:has()` | Parent state (a card with a checked radio, a page with an open drawer) |
| `color-mix(in oklab, ...)` | Tints and hovers from tokens |
| `text-wrap: balance` / `pretty` | Headings / paragraphs |
| `aspect-ratio` | Media boxes, instead of padding hacks |
| `translate`, `scale`, `rotate` properties | Motion without overwriting `transform` |
| `@property` | Animating or scaling with custom properties |
| `inset`, `gap`, `place-items` | Shorter, clearer layout |
| `:focus-visible` | Keyboard focus rings |
| View transitions | Page-to-page morphs where the page supports them |

## Private Custom Properties

- Component knobs start with `--_`: `--_dot`, `--_a`, `--_b`.
- Set the default on the block, change it in a modifier, a data attribute or an inline `style="--_a: ..."`.
- Never read a `--_` variable from another block.

```css
.orb-fact { --_a: var(--primary-100); --_b: var(--error-100); background: linear-gradient(130deg, var(--_a), var(--_b)); }
.orb-fact--switch { --_a: var(--info-100); --_b: var(--success-100); }
```

## Specificity and `!important`

- Keep specificity flat: one class, plus a state or attribute when needed.
- No id selectors and no type-first selectors for styling.
- `!important` only to beat a third party's `!important` or a rule inside Bricks' `@layer bricks`. Write a comment on the line saying which one.
- To beat TwoKit's `.bricks-button` on a Bricks button: `.my-btn:is(.bricks-button, button)`.

## Stacking (z-index)

TwoKit has no z-index tokens. Use one small scale:

- Inside a component: `isolation: isolate` on the block, then only `1`, `2`, `3` inside it.
- Site layers, defined once as custom properties and never as raw numbers: sticky header, buy bar, drawer or offcanvas, dialog, toast.

## Accessibility In CSS

- Never remove a focus outline without drawing a replacement. Prefer `:focus-visible`; plain `:focus` only for things that must react to any focus (floating labels).
- iPhone Safari shows `:focus-visible` on a tapped radio or checkbox: keep card focus rings inside `@media (hover: hover) and (pointer: fine)` when a ring on tap would look broken.
- Visually hidden text uses a clip pattern, never `display: none` (screen readers skip that).
- Lock page scroll on `:root`, and keep `body` visible: `:root:has(.drawer.brx-open) { overflow: hidden; & body { overflow: visible; } }`. Sticky elements break otherwise.

## Bricks and TwoKit Facts That Change How You Write CSS

- TwoKit makes every Bricks Div `display: flex; flex-direction: column`. State the display you want.
- Bricks' own element CSS sits in `@layer bricks`, so a plain class beats it, except where Bricks uses `!important` inside the layer.
- Bricks gives Divs `max-width: 100%`. A child that must be wider (slider cards) needs `max-inline-size: none`.
- Bricks Block elements wrap by default: set `flex-wrap: nowrap` on a Block used as a row.
- Bricks Offcanvas content is `align-items: flex-start`: set `align-items: stretch` on the panel.
- CSS for markup printed by a shortcode or plugin must hang off a class on the element that prints it.

## File Header

Start each stylesheet with the element tree, one line per class and the Bricks element it becomes. The build script and the next person read it.

```css
/* Product row (Figma 45:1012)
   section.product-row            Section
     .product-row__head           Div
       h2.product-row__title      Heading
     ul.product-row__grid         Div (tag ul), Products loop
       li.product-card            Div (tag li)
*/
```

## Review Checklist

Before shipping a stylesheet:

1. Every class is BEM, every rule starts with its own class, nothing is nested as `&__`.
2. No physical property except `overflow-x/y`.
3. Every spacing, type, colour, radius, shadow and timing value is a TwoKit token, or one of the raw-value exceptions.
4. Components that change layout with their own width use a named container query, never on a grid or grid item.
5. Media queries use range syntax, px, and the site's breakpoints.
6. Motion has a reduced-motion branch. Hover effects are limited to fine pointers.
7. No `!important` without a comment naming the third party. No raw z-index outside the scale.
8. The header element tree matches the markup.

The Brickwright library already enforces 1 and 3 (unknown variables, raw colours, raw lengths as warnings) and refuses element CSS. Checks for 2, 5 and 7 are planned.
