# file: app.py
import streamlit as st
import requests
import re
import tempfile
import os

st.set_page_config(page_title="Reverb Draft Creator", layout="centered")
st.title("Reverb Draft Creator (With Manual Photo Upload)")

st.markdown("""
Clone a listing's metadata to a draft on your account, and optionally upload your own photos.
""")

token = st.text_input("Reverb API Token", type="password")
url = st.text_input("Reverb Listing URL")

# Allow multiple file uploads for photos
uploaded_files = st.file_uploader(
    "Upload photos to attach to the draft", 
    type=["png", "jpg", "jpeg"], 
    accept_multiple_files=True
)

BASE_API = "https://api.reverb.com/api"

def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept-Version": "3.0",
        "Accept": "application/hal+json",
    }

def extract_listing_id(url):
    if "reverb.com/item/" not in url:
        return None
    part = url.split("/item/")[1].split("?")[0]
    m = re.match(r"^(\d+)", part)
    return m.group(1) if m else None

if st.button("Create Draft"):
    if not token or not url:
        st.error("Please provide API token and listing URL.")
        st.stop()

    listing_id = extract_listing_id(url)
    if not listing_id:
        st.error("Invalid Reverb listing URL.")
        st.stop()

    # -------------------------------------------------
    # 1. Fetch listing metadata
    # -------------------------------------------------
    st.info(f"Fetching listing {listing_id} metadata...")
    r = requests.get(f"{BASE_API}/listings/{listing_id}", headers=headers(token))
    if r.status_code != 200:
        st.error("Failed to fetch listing metadata.")
        st.code(r.text)
        st.stop()

    listing = r.json()

    # -------------------------------------------------
    # 2. Create draft listing
    # -------------------------------------------------
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

    st.info("Creating draft listing...")
    draft = requests.post(
        f"{BASE_API}/listings",
        headers={**headers(token), "Content-Type": "application/json"},
        json=payload
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
    # 3. Upload user-provided photos
    # -------------------------------------------------
    if uploaded_files:
        st.info(f"Uploading {len(uploaded_files)} photo(s)...")
        for idx, file in enumerate(uploaded_files, start=1):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name

            with open(tmp_path, "rb") as img:
                upload = requests.post(
                    f"{BASE_API}/listings/{draft_id}/photos",
                    headers=headers(token),
                    files={"photo": img},
                )

            os.unlink(tmp_path)

            if upload.status_code not in (200, 201):
                st.warning(f"Failed to upload photo {idx}: {file.name}")
            else:
                st.success(f"Uploaded photo {idx}: {file.name}")
    else:
        st.info("No photos uploaded. You can add them later from Reverb.")

    st.success("✅ Draft ready!")
