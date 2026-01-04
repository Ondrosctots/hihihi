# file: app.py
import streamlit as st
import requests
import re
import tempfile
import os

st.set_page_config(page_title="Reverb Draft Creator", layout="centered")
st.title("Reverb Draft Creator (WITH Photos)")

st.markdown("""
This tool copies an existing Reverb listing **including photos**
and creates it as a **draft** on your own account.
""")

token = st.text_input("Reverb API Token", type="password")
url = st.text_input("Reverb Listing URL")

BASE_API = "https://api.reverb.com/api"

HEADERS = lambda t: {
    "Authorization": f"Bearer {t}",
    "Accept-Version": "3.0",
    "Accept": "application/hal+json",
}

def extract_listing_id(url):
    if "reverb.com/item/" not in url:
        return None
    part = url.split("/item/")[1].split("?")[0]
    match = re.match(r"^(\d+)", part)
    return match.group(1) if match else None

if st.button("Create Draft with Photos"):
    if not token or not url:
        st.error("Please provide both API token and listing URL.")
        st.stop()

    listing_id = extract_listing_id(url)
    if not listing_id:
        st.error("Invalid Reverb listing URL.")
        st.stop()

    # -------------------------------------------------
    # 1. Fetch original listing
    # -------------------------------------------------
    st.info(f"Fetching listing {listing_id}...")
    r = requests.get(f"{BASE_API}/listings/{listing_id}", headers=HEADERS(token))

    if r.status_code != 200:
        st.error("Failed to fetch listing.")
        st.code(r.text)
        st.stop()

    listing = r.json()

    payload = {
        "title": listing.get("title", ""),
        "description": listing.get("description", ""),
        "brand": listing.get("make", ""),
        "model": listing.get("model", ""),
        "price": {
            "amount": listing.get("price", {}).get("amount", "1.00"),
            "currency": listing.get("price", {}).get("currency", "USD"),
        },
        "state": "draft",
    }

    # -------------------------------------------------
    # 2. Create draft listing
    # -------------------------------------------------
    st.info("Creating draft listing...")
    draft = requests.post(
        f"{BASE_API}/listings",
        headers={**HEADERS(token), "Content-Type": "application/json"},
        json=payload,
    )

    if draft.status_code not in (200, 201):
        st.error("Draft creation failed.")
        st.code(draft.text)
        st.stop()

    draft_data = draft.json()
    draft_id = draft_data.get("id") or draft_data.get("listing", {}).get("id")

    if not draft_id:
        st.error("Draft ID not returned by API.")
        st.stop()

    st.success(f"Draft created! ID: {draft_id}")

    # -------------------------------------------------
    # 3. Fetch original photos
    # -------------------------------------------------
    photos = listing.get("_embedded", {}).get("photos", [])
    if not photos:
        st.warning("No photos found on original listing.")
        st.stop()

    st.info(f"Copying {len(photos)} photos...")

    # -------------------------------------------------
    # 4. Download & upload photos
    # -------------------------------------------------
    for idx, photo in enumerate(photos, start=1):
        photo_url = photo.get("_links", {}).get("full", {}).get("href")
        if not photo_url:
            continue

        # Download image
        img_response = requests.get(photo_url, stream=True)
        if img_response.status_code != 200:
            st.warning(f"Failed to download photo {idx}")
            continue

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            for chunk in img_response.iter_content(1024):
                tmp.write(chunk)
            tmp_path = tmp.name

        # Upload image
        with open(tmp_path, "rb") as img:
            files = {"photo": img}
            upload = requests.post(
                f"{BASE_API}/listings/{draft_id}/photos",
                headers=HEADERS(token),
                files=files,
            )

        os.unlink(tmp_path)

        if upload.status_code not in (200, 201):
            st.warning(f"Failed to upload photo {idx}")
        else:
            st.success(f"Uploaded photo {idx}")

    st.success("✅ Draft fully created with photos!")
