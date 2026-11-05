# HTML Rules

Read this when writing mockup HTML that will become Bricks elements, a shortcode's markup, or when reviewing a page's structure. Pairs with [css.md](css.md) (styling) and [copywriting.md](copywriting.md) (the words).

These are defaults. A project's own standard always wins; use this where there is none.

The mockup HTML is the plan for the Bricks element tree: every tag and class here becomes an element and a global class.

## Structure

- One `<h1>` per page. Headings never skip a level: a card grid under an `h1` needs an `h2` (visible or visually hidden) before card titles can be `h3`.
- Sections are `<section>` with a heading, labelled by it: `aria-labelledby="faq-title"` on the section, `id="faq-title"` on the heading.
- Don't add `<main>`, `<header>` or `<footer>` around page content: the theme and Bricks templates already print them.
- Use the element that means the thing:

| Content | Element |
| --- | --- |
| A list of cards, links, steps | `ul` / `ol` > `li` (Bricks Div with tag `ul` / `li`) |
| A self-contained card or post | `article` |
| Side content, help boxes | `aside` |
| Navigation | `nav` with an `aria-label` |
| Image + caption | `figure` > `figcaption` |
| Facts as label and value | `dl` > `dt` + `dd` |
| Show/hide without JavaScript | `details` > `summary` |
| Modal | `dialog` |
| Quote, review | `blockquote` (and set the font: themes often style it as Georgia) |
| Dates | `time` with `datetime` |
| Actions | `button type="button"` (or `submit`). Links only go somewhere. |

- `<p>` and headings can't contain a `<div>`: the browser closes the paragraph early. Inside them use `span` (in Bricks: a Div with custom tag `span`).

## Links and Buttons

- Every `<a>` has a real `href` (in Bricks: a dynamic link or the real URL). `href="#"` is a mockup placeholder only.
- Every `<button>` has a `type`.
- A whole clickable card: the card gets TwoKit's `clickable-card`, the heading gets the link (`h3 > a`). Don't wrap the card in an `<a>`.
- Icon-only buttons need a name: `aria-label`, or visually hidden text inside.
- A Bricks toggle that should also work without JavaScript can be a real link (`a.cart-btn href="/cart/"`) with the interaction on top.

## Images and Icons

- Every `img` has `alt`. Decorative images: `alt=""`. Content images: describe what's in them (see [copywriting.md](copywriting.md)).
- `width` and `height` on every image, so the page doesn't jump.
- Below the fold: `loading="lazy"`. The hero image: eager, never lazy.
- Decorative SVGs: `aria-hidden="true"` and `focusable="false"`. Icons come from the site's icon set (uploaded SVG files), not inline code (Bricks needs a code signature for inline SVG code).

## Forms

- Every field has a visible `<label>` (or a floating label), never a placeholder alone.
- Set `autocomplete` (`email`, `given-name`, `postal-code`, `tel`...) and the right `type` / `inputmode`.
- Group related choices in `fieldset` + `legend`.
- Error messages are linked to their field (`aria-describedby`) and say what to do next.

## Attributes

- `id` only for anchors, `aria-*` references and labels. Never for styling.
- State lives in `data-*` attributes (`data-state="open"`) or ARIA (`aria-expanded`, `aria-current`), and CSS reads them.
- Inside query loops Bricks leaves accordion ids and ARIA references empty: set them yourself with the loop item id (`faq-a-{post_id}`).
- Never use Bricks' reserved attributes: `data-component`, `data-component-id`, `data-id`, `data-parent-id`, `data-script-id`, `data-element-id`, `data-index`. They lock selection in the builder.
- No `onclick` or other inline handlers. No inline `style` except passing custom properties (`style="--_tint: var(--info-100)"`).
- No supplier or source names anywhere a browser receives: text, attributes, classes, ids, comments, file names.

## Review Checklist

1. One `h1`, no skipped heading levels, sections labelled by their headings.
2. Lists are lists, cards are `article`s, actions are `button`s with a `type`, links have real URLs.
3. Every image: `alt`, `width`, `height`, `loading`. Decorative SVGs hidden.
4. Every field: label, `autocomplete`, right `type`.
5. `id`s only for anchors and ARIA; state in `data-*` or ARIA; no reserved Bricks attributes; no inline handlers.
