# Photos and videos

`uploadAdPhoto`, `uploadAdVideo`, `uploadWebsitePhoto`.

Media is uploaded first, then referenced by id when you create or edit an ad.

```python
photo = client.upload_ad_photo("banner.jpg")

client.create_ad(
    ...,
    photo_id=photo.photo_id,
)
```

## What each upload accepts

| Method | Format | Size | Dimensions |
|---|---|---|---|
| `upload_ad_photo` | JPEG or PNG | ≤ 5 MB | ≥ 640 px wide, 16:9 |
| `upload_ad_video` | MP4 | ≤ 20 MB | ≥ 640 px wide, 16:9, 3–60 seconds |
| `upload_website_photo` | JPEG or PNG | ≤ 1 MB | ≥ 150 × 150 px |

The library checks the format (from the file's first bytes, falling back to its name) and the size before uploading. Dimensions, aspect ratio and duration are checked by the API.

## Passing the file

Each upload method takes a path, `bytes`, or a file opened in binary mode:

```python
client.upload_ad_photo("banner.jpg")
client.upload_ad_photo(Path("assets") / "banner.png")
client.upload_ad_photo(image_bytes, filename="banner.png")

with open("teaser.mp4", "rb") as handle:
    video = client.upload_ad_video(handle)
```

`filename` names the upload; it defaults to the path's or file object's own name.

## Photo or video in an ad

```python
video = client.upload_ad_video("teaser.mp4")

client.create_ad(
    title="Launch — video",
    text="Sixty seconds on what's new.",
    video_id=video.video_id,
    promote_url="https://t.me/mychannel",
    cpm=4,
    placement="channel_post",
    target=InputAdTargetChannels(language_codes=["en"]),
    initial_budget=30,
)
```

* An ad has a photo **or** a video, not both.
* Media applies to **channels** and **users** targeting only.
* Media raises the CPM an ad needs to be shown — by 50–80 % for a photo and 70–100 % for a video, on average, according to the API docs.
* Setting a new `photo_id` or `video_id` with `edit_ad` replaces whatever the ad had.

The returned `Ad` carries `ad.photo` (`AdPhoto`) or `ad.video` (`AdVideo`), each with an id and a URL.

## Website photo

An ad promoting an external website can carry the site's name and a picture of it:

```python
site_photo = client.upload_website_photo("logo.png")

client.create_ad(
    title="Shop — autumn sale",
    text="Everything 30 % off until Sunday.",
    promote_url="https://shop.example.com/sale",
    website_name="Example Shop",           # required for an external link, 1–40 characters
    website_photo_id=site_photo.photo_id,
    button="buy",
    cpm=2,
    placement="channel_post",
    target=InputAdTargetUsers(country_codes=["DE"]),
)
```

## Ids belong to one account

A photo or video id is unique to the account that uploaded it and cannot be used from another account. When you work with related accounts, upload into the account that will run the ad:

```python
acme = client.with_account("rel-123")
photo = acme.upload_ad_photo("banner.jpg")
acme.create_ad(..., photo_id=photo.photo_id)
```
