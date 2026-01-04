# file: app.py
import streamlit as st
import requests
import re

st.set_page_config(page_title="Reverb Draft Creator", layout="centered")
st.title("Reverb Draft Creator (Manual Photo Upload with Preview)")

st.markdown("""
Clone a listing's metadata to a draft on your account, and upload your own photos.
Preview your photos before creating the draft.
""")

token = st.text_input("Reverb API Token", type="password")
url = st.text_input("Reverb Listing URL")

# Upload multiple images
uploaded_files = st.file_uploader(
    "Upload photos to attach to the draft",
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

def upload_headers(token):
    # Simplified headers for uploads (no Accept-Version or Accept to avoid conflicts)
    return {
        "Authorization": f"Bearer {token}",
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

    # -------------------------
    # 3. Upload user photos (Two-step process with extensive debugging)
    # -------------------------
    if uploaded_files:
        st.info(f"Uploading {len(uploaded_files)} photo(s)...")
        for idx, file in enumerate(uploaded_files, start=1):
            try:
                file.seek(0)  # Reset pointer
                
                # Debug: Log request details (without token)
                st.info(f"Debug: Preparing upload for {file.name}")
                st.write(f"Debug: Endpoint: {BASE_API}/my/photos")
                st.write(f"Debug: Method: POST")
                st.write(f"Debug: Headers: Authorization (Bearer [REDACTED]), Content-Type: multipart/form-data")
                st.write(f"Debug: File: {file.name}, Size: {len(file.read())} bytes")
                file.seek(0)  # Reset after reading size
                
                # Debug: Test if endpoint exists with a GET request
                st.info("Debug: Testing endpoint existence with GET request...")
                test_get = requests.get(f"{BASE_API}/my/photos", headers=upload_headers(token))
                st.write(f"Debug: GET /my/photos status: {test_get.status_code}")
                if test_get.status_code == 404:
                    st.warning("Debug: GET /my/photos also returns 404 - endpoint likely doesn't exist.")
                else:
                    st.write(f"Debug: GET response: {test_get.text[:500]}...")  # Truncate for brevity
                
                # Step 1: Attempt upload with current endpoint
                st.info("Debug: Attempting POST upload...")
                upload_response = requests.post(
                    f"{BASE_API}/my/photos",
                    headers=upload_headers(token),
                    files={"photo": (file.name, file, "image/jpeg")},
                )
                st.write(f"Debug: POST status: {upload_response.status_code}")
                st.write(f"Debug: POST response headers: {dict(upload_response.headers)}")
                st.write(f"Debug: POST response body: {upload_response.text}")
                
                if upload_response.status_code not in (200, 201):
                    st.warning(f"Failed to upload photo {idx}: {file.name} (Step 1 failed)")
                    
                    # Debug: Try alternative endpoint (/photos without /my/)
                    st.info("Debug: Trying alternative endpoint /photos (no /my/)...")
                    alt_upload = requests.post(
                        f"{BASE_API}/photos",
                        headers=upload_headers(token),
                        files={"photo": (file.name, file, "image/jpeg")},
                    )
                    st.write(f"Debug: ALT POST /photos status: {alt_upload.status_code}")
                    st.write(f"Debug: ALT response: {alt_upload.text}")
                    
                    if alt_upload.status_code in (200, 201):
                        st.success("Debug: Alternative endpoint worked! Using it for photo ID.")
                        photo_data = alt_upload.json()
                    else:
                        continue  # Skip if both fail
                else:
                    photo_data = upload_response.json()
                
                photo_id = photo_data.get("id")
                if not photo_id:
                    st.warning(f"No photo ID returned for {file.name}")
                    st.code(f"Response data: {photo_data}")
                    continue
                
                # Step 2: Associate the photo with the draft listing
                st.info(f"Debug: Associating photo ID {photo_id} with draft {draft_id}")
                associate_response = requests.post(
                    f"{BASE_API}/my/listings/{draft_id}/photos",
                    headers={**upload_headers(token), "Content-Type": "application/json"},
                    json={"photo_id": photo_id}
                )
                st.write(f"Debug: Associate POST status: {associate_response.status_code}")
                st.write(f"Debug: Associate response: {associate_response.text}")
                
                if associate_response.status_code not in (200, 201):
                    st.warning(f"Failed to associate photo {idx}: {file.name} (Step 2 failed)")
                else:
                    st.success(f"Uploaded and associated photo {idx}: {file.name}")
            
            except Exception as e:
                st.error(f"Exception uploading photo {idx}: {file.name}")
                st.code(str(e))
    else:
        st.info("No photos uploaded. You can add them later from Reverb.")

    st.success("✅ Draft ready!")
