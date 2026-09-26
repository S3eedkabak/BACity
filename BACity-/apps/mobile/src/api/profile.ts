import { Platform } from "react-native";
import type { ImagePickerAsset } from "expo-image-picker";
import { API_URL, ApiError } from "./client";
import { getSessionToken } from "../store/tokenSession";

export async function uploadAvatar(asset: ImagePickerAsset): Promise<void> {
  const form = new FormData();
  if (Platform.OS === "web") {
    const blob = await fetch(asset.uri).then((response) => response.blob());
    form.append("avatar", blob, asset.fileName ?? "avatar.jpg");
  } else {
    form.append("avatar", {
      uri: asset.uri,
      name: asset.fileName ?? "avatar.jpg",
      type: asset.mimeType ?? "image/jpeg",
    } as any);
  }
  const token = getSessionToken();
  const response = await fetch(`${API_URL}/community/profile/avatar`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });
  if (!response.ok) {
    let message = response.statusText;
    try { message = (await response.json()).detail ?? message; } catch {}
    throw new ApiError(response.status, message);
  }
}
