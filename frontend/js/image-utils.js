const MAX_INPUT_BYTES = 25 * 1024 * 1024; // refuse huge files before decoding them

function toBlob(canvas, type, quality) {
  return new Promise(resolve => canvas.toBlob(resolve, type, quality));
}

/**
 * Turn a chosen .jpg or .png into a JPEG File under maxBytes.
 * The file is named photo.jpg because the backend checks the extension.
 */
export async function compressImage(file, maxBytes = 450 * 1024) {
  if (!['image/jpeg', 'image/png'].includes(file.type)) {
    throw new Error('Choose a .jpg or .png photo.');
  }
  if (file.size > MAX_INPUT_BYTES) {
    throw new Error('That photo is too large. Choose one under 25 MB.');
  }

  let bitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error('That file could not be read as an image.');
  }

  try {
    let longestSide = 1600;
    for (let attempt = 0; attempt < 6; attempt++) {
      const scale = Math.min(1, longestSide / Math.max(bitmap.width, bitmap.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(bitmap.width * scale));
      canvas.height = Math.max(1, Math.round(bitmap.height * scale));

      const context = canvas.getContext('2d');
      context.fillStyle = '#ffffff'; // JPEG has no transparency
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

      for (const quality of [0.85, 0.75, 0.65, 0.55]) {
        const blob = await toBlob(canvas, 'image/jpeg', quality);
        if (blob && blob.size <= maxBytes) {
          return new File([blob], 'photo.jpg', { type: 'image/jpeg' });
        }
      }
      longestSide = Math.round(longestSide * 0.75); // still too big: make it smaller
    }
  } finally {
    bitmap.close?.();
  }
  throw new Error('Could not shrink that photo enough. Try a different one.');
}