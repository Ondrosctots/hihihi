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
    # Include Accept-Version for uploads (might be required)
    return {
        "Authorization": f"Bearer {token}",
        "Accept-Version": "3.0",
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
    # 3. Upload user photos (Two-step process with extensive debugging and alternatives)
    # -------------------------
    if uploaded_files:
        st.info(f"Uploading {len(uploaded_files)} photo(s)...")
        for idx, file in enumerate(uploaded_files, start=1):
            try:
                file.seek(0)  # Reset pointer
                
                # Debug: Log request details (without token)
                st.info(f"Debug: Preparing upload for {file.name}")
                st.write(f"Debug: File size: {len(file.read())} bytes")
                file.seek(0)
                
                success = False
                
                # Attempt 1: Direct upload to listing photos endpoint
                st.info("Debug: Attempt 1 - Direct upload to /my/listings/{draft_id}/photos")
                direct_upload = requests.post(
                    f"{BASE_API}/my/listings/{draft_id}/photos",
                    headers=upload_headers(token),
                    files={"photo": (file.name, file, "image/jpeg")},
                )
                st.write(f"Debug: Direct upload status: {direct_upload.status_code}")
                st.write(f"Debug: Direct upload response: {direct_upload.text}")
                if direct_upload.status_code in (200, 201):
                    st.success(f"Debug: Direct upload worked for photo {idx}!")
                    success = True
                    continue
                
                # Attempt 2: Try "file" key instead of "photo"
                st.info("Debug: Attempt 2 - Using 'file' key instead of 'photo'")
                file_upload = requests.post(
                    f"{BASE_API}/my/listings/{draft_id}/photos",
                    headers=upload_headers(token),
                    files={"file": (file.name, file, "image/jpeg")},
                )
                st.write(f"Debug: File key upload status: {file_upload.status_code}")
                st.write(f"Debug: File key response: {file_upload.text}")
                if file_upload.status_code in (200, 201):
                    st.success(f"Debug: File key upload worked for photo {idx}!")
                    success = True
                    continue
                
                # Attempt 3: Try presigned URL flow (request URL first)
                st.info("Debug: Attempt 3 - Presigned URL flow")
                presign_request = requests.post(
                    f"{BASE_API}/my/listings/{draft_id}/photos/presigned_url",
                    headers={**upload_headers(token), "Content-Type": "application/json"},
                    json={"filename": file.name, "content_type": "image/jpeg"}
                )
                st.write(f"Debug: Presign request status: {presign_request.status_code}")
                st.write(f"Debug: Presign response: {presign_request.text}")
                if presign_request.status_code in (200, 201):
                    presign_data = presign_request.json()
                    upload_url = presign_data.get("url") or presign_data.get("upload_url")
                    if upload_url:
                        st.write(f"Debug: Uploading to presigned URL: {upload_url}")
                        presign_upload = requests.put(
                            upload_url,
                            data=file.read(),
                            headers={"Content-Type": "image/jpeg"}
                        )
                        st.write(f"Debug: Presign upload status: {presign_upload.status_code}")
                        if presign_upload.status_code in (200, 201):
                            st.success(f"Debug: Presigned upload worked for photo {idx}!")
                            success = True
                            continue
                
                # Attempt 4: Try /photos without /my/ with "file" key
                st.info("Debug: Attempt 4 - /photos with 'file' key")
                alt_file_upload = requests.post(
                    f"{BASE_API}/photos",
                    headers=upload_headers(token),
                    files={"file": (file.name, file, "image/jpeg")},
                )
                st.write(f"Debug: Alt file upload status: {alt_file_upload.status_code}")
                st.write(f"Debug: Alt file response: {alt_file_upload.text}")
                if alt_file_upload.status_code in (200, 201):
                    photo_data = alt_file_upload.json()
                    photo_id = photo_data.get("id")
                    if photo_id:
                        # Associate
                        associate_response = requests.post(
                            f"{BASE_API}/my/listings/{draft_id}/photos",
                            headers={**upload_headers(token), "Content-Type": "application/json"},
                            json={"photo_id": photo_id}
                        )
                        if associate_response.status_code in (200, 201):
                            st.success(f"Debug: Alt file + associate worked for photo {idx}!")
                            success = True
                            continue
                
                if not success:
                    st.error(f"All upload attempts failed for photo {idx}: {file.name}. Check token permissions or API docs.")
            
            except Exception as e:
                st.error(f"Exception uploading photo {idx}: {file.name}")
                st.code(str(e))
    else:
        st.info("No photos uploaded. You can add them later from Reverb.")

    st.success("✅ Draft ready!")
