# asset-forward-design Specification

## Purpose
The template pool's actual visual material — example pages and image
sets — reaches the design session and the coder, classified and
uncapped.

## Requirements

### Requirement: materialized material is classified and bounded by flags

design-materialize SHALL classify every manifest entry with a kind
(image/svg/css/html/data/text) and publish a counts map, and SHALL
honor --max-files/--max-bytes overrides over defaults sized to carry
the pool's image-bearing templates (40 files / 24MB).

#### Scenario: nominal

- **WHEN a template with png, svg, css and example.html is
  materialized**
- **THEN each entry carries its kind and counts reads images=1,
  svg=1, css=1, html=1**

### Requirement: the design session derives from standing material

When materialized material stands before design-specify runs, the
specify prompt SHALL order the ui-designer to derive design/tokens.css
from the materialized example page's actual visual system and to
reference the materialized images by their materialized paths; with no
standing material the prompt SHALL be unchanged.

#### Scenario: nominal

- **WHEN a materialized example.html and one image stand**
- **THEN the prompt names the example path, says the palette MUST
  derive from it, and lists the image path**

### Requirement: tourism vocabulary reaches the image-bearing template

scripts/od-synonyms.json SHALL bridge tourism terms
(旅游官网/观光/景点/目的地/带图官网/旅游页/风景页/图库落地页) to
open-design-landing and to no other template.

#### Scenario: nominal

- **WHEN the table is loaded**
- **THEN open-design-landing carries the tourism terms and no other
  template does**
