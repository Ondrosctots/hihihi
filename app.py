# file: app.py
import streamlit as st
import requests
import re

st.set_page_config(page_title="Reverb Draft Creator", layout="centered")
st.title("Reverb Draft Creator (Manual Photo Upload with Preview)")

st.markdown("""
Clone a listing's metadata to a draft on your account, and upload your own photos.
Preview your photos before creating the draft.

**Note**: Photo uploads via API are currently failing (404 errors). Upload photos manually in Reverb after creating the draft.
""")

token = st.text_input("Reverb API Token", type="password")
url = st.text_input("Reverb Listing URL")

# Upload multiple images (for preview only)
uploaded_files = st.file_uploader(
    "Upload photos to attach to the draft (preview only - upload manually in Reverb)",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True
)

# Preview uploaded images
if uploaded_files:
    st.markdown("### Photo Preview")
    for file in uploaded_files:
        file.seek(0)
        st.image(file, width=200)
        file.seek(0)  # Reset pointer for later upload

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

    # -------------------------
    # 1. Fetch listing metadata
    # -------------------------
    st.info(f"Fetching listing {listing_id} metadata...")
    r = requests.get(f"{BASE_API}/listings/{listing_id}", headers=headers(token))
    if r.status_code != 200:
        st.error("Failed to fetch listing metadata.")
        st.code(r.text)
        st.stop()

    listing = r.json()

    # -------------------------
    # 2. Create draft listing
    # -------------------------
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
    st.info(f"📝 To add photos: Go to https://reverb.com/my/listings/{draft_id} and upload manually.")

    # -------------------------
    # 3. Photo upload (disabled due to API issues)
    # -------------------------
    if uploaded_files:
        st.warning("Photo uploads via API are currently not working (404 errors). Please upload them manually in the draft listing above.")
    else:
        st.info("No photos uploaded. You can add them later from Reverb.")

    st.success("✅ Draft ready!")
