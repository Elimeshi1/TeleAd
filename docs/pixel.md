# Pixel and conversions

`createPixel`, `getPixel`, `createPixelEvent`, `editPixelEvent`, `deletePixelEvent`, `getPixelEventsById`, `getPixelEventsList`.

For an ad that sends people to a website, the **Pixel Tag** measures what they do there. It has two parts: a base snippet on every page, and **events** for the actions you count as conversions.

!!! note "Not every account has the pixel"
    If the account has no access to the Pixel Tag, every method here raises `PermissionDeniedError` with the code `ACCESS_DENIED`.

## 1. Create the pixel

Once per account:

```python
pixel = client.create_pixel()
print(pixel.code_snippet)        # place before </head> on every page of the site
```

Later, `client.get_pixel()` returns the same object.

## 2. Create events

```python
event = client.create_pixel_event("Checkout completed", "purchase")
if event.code_snippet:
    print(event.code_snippet)    # place it where the action happens
```

Some events need a snippet of their own; others work from the base code alone, and then `code_snippet` is `None`.

Event types: `page_view`, `add_to_cart`, `add_to_wishlist`, `customize_product`, `initiate_checkout`, `add_payment_info`, `purchase`, `contact`, `lead`, `schedule`, `complete_registration`, `submit_application`, `start_trial`, `subscribe`, `view_content`, `search`, `find_location`, `donate`, `custom`.

## 3. Attach an event to an ad

```python
client.create_ad(
    ...,
    promote_url="https://shop.example.com/sale",
    website_name="Example Shop",
    conversion_event_id=event.event_id,
)
```

`conversion_event_id` applies to external links only, and **cannot be changed** once set. The ad's `actions` then counts that event, and `ad.action_type` names it. See [Stats → actions](stats.md#actions-and-conversions).

## Events you already have

```python
for event in client.get_pixel_events_list():
    print(event.event_id, event.title, event.type, event.status, event.last_triggered_at)
```

| Field | |
|---|---|
| `status` | `active` or `inactive` |
| `ads_count` | ads using it as their conversion event |
| `last_triggered_date` | `None` if never triggered, or not in the last 7 days |
| `auto_created` | created by the platform — such an event can be neither edited nor deleted |

## Rename or delete

```python
client.edit_pixel_event(event_id, "Purchase (new checkout)")    # 1–64 bytes
client.delete_pixel_event(event_id)                             # no ad may use it
```
