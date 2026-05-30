# Brand assets

These images are prepared for submission to the
[home-assistant/brands](https://github.com/home-assistant/brands) repository.
Home Assistant and HACS fetch integration icons from
`https://brands.home-assistant.io/<domain>/icon.png`, **not** from the
integration folder — so the icon only appears in the HA UI after the brands PR
is merged.

## Layout

```
custom_integrations/tfiac_local/
├── icon.png      (256x256, transparent)
└── icon@2x.png   (512x512, transparent)
```

## How to submit

1. Fork `home-assistant/brands`.
2. Copy `brands/custom_integrations/tfiac_local/` into the fork's
   `custom_integrations/` directory.
3. Open a pull request. Once merged, the icon shows for the `tfiac_local`
   domain in Home Assistant and HACS.

The source artwork lives in [`../assets/icon.svg`](../assets/icon.svg).
