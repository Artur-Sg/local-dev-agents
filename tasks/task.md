Fix the layout issues and polish the existing bakery landing page.

Current problems:
- The "View Menu" CTA appears as a bar at the bottom of the page. This is wrong.
- The CTA must appear only inside the hero section.
- The page content is too stretched horizontally.
- The hero section looks too empty.
- The landing page should feel more polished and modern.

Requirements:
- Keep using only index.html and styles.css.
- The project root is the sandbox root.
- Write only these files:
  - index.html
  - styles.css
  - tests/test_landing.py
- Do not create app/.
- Do not create landing-page/.
- Do not create nested project directories.
- Do not modify tooling/, calc_app/, authorization/, main.py, test_main.py, or requirements.txt.
- Do not add JavaScript.
- Do not use external images, CDN links, fonts, or remote assets.
- Do not use img tags.
- Preserve all existing realistic bakery content.
- Do not reintroduce placeholder content.

Layout fixes:
- Remove any fixed or sticky positioning from the CTA.
- The CTA link must be inside the hero section and link to #menu.
- Add a centered max-width container for main content.
- Hero section should have strong visual presence:
  - warm background
  - centered content
  - headline
  - subtitle
  - CTA button below subtitle
- Menu cards must stay inside the content container.
- Product cards should use responsive grid layout.
- Testimonials should be cards inside the same centered container.
- Contact section should be visually distinct but not oversized.

Design requirements:
- Warm artisan bakery color palette.
- Better section spacing.
- Rounded cards.
- Subtle shadows.
- Hover states.
- Mobile responsive layout.
- Finished landing page look, not a wireframe.

Tests:
- Update tests/test_landing.py if needed.
- Tests must verify:
  - CTA href is "#menu"
  - there is no "position: fixed" in styles.css
  - there is no "position: sticky" in styles.css
  - placeholder strings are absent
  - product-card and testimonial-card elements exist
  - styles.css contains display: grid, border-radius, box-shadow, :hover, and @media

Do not modify unrelated files.

Return only file blocks using safe relative paths.

Required output format:

### FILE: relative/path/from/repo/root
<full file content>
