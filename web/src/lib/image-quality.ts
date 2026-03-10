export interface QualityCheck {
  passed: boolean;
  blur: { passed: boolean; score: number };
  dimensions: { passed: boolean; width: number; height: number };
  fileSize: { passed: boolean; bytes: number };
}

const MIN_WIDTH = 640;
const MIN_HEIGHT = 480;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MIN_FILE_SIZE = 10 * 1024; // 10KB
const BLUR_THRESHOLD = 15;

function detectBlur(imageData: ImageData): number {
  const { data, width, height } = imageData;
  let sum = 0;
  let count = 0;

  for (let y = 1; y < height - 1; y++) {
    for (let x = 1; x < width - 1; x++) {
      const idx = (y * width + x) * 4;
      const gray =
        data[idx] * 0.299 + data[idx + 1] * 0.587 + data[idx + 2] * 0.114;

      const left =
        data[idx - 4] * 0.299 +
        data[idx - 3] * 0.587 +
        data[idx - 2] * 0.114;
      const right =
        data[idx + 4] * 0.299 +
        data[idx + 5] * 0.587 +
        data[idx + 6] * 0.114;
      const top =
        data[((y - 1) * width + x) * 4] * 0.299 +
        data[((y - 1) * width + x) * 4 + 1] * 0.587 +
        data[((y - 1) * width + x) * 4 + 2] * 0.114;
      const bottom =
        data[((y + 1) * width + x) * 4] * 0.299 +
        data[((y + 1) * width + x) * 4 + 1] * 0.587 +
        data[((y + 1) * width + x) * 4 + 2] * 0.114;

      const laplacian = Math.abs(left + right + top + bottom - 4 * gray);
      sum += laplacian;
      count++;
    }
  }

  return count > 0 ? sum / count : 0;
}

export async function checkImageQuality(file: File): Promise<QualityCheck> {
  const fileSizeCheck = {
    passed: file.size >= MIN_FILE_SIZE && file.size <= MAX_FILE_SIZE,
    bytes: file.size,
  };

  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);

    img.onload = () => {
      const dimensionsCheck = {
        passed: img.width >= MIN_WIDTH && img.height >= MIN_HEIGHT,
        width: img.width,
        height: img.height,
      };

      const canvas = document.createElement("canvas");
      const scale = Math.min(1, 800 / Math.max(img.width, img.height));
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;

      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const blurScore = detectBlur(imageData);
      const blurCheck = { passed: blurScore >= BLUR_THRESHOLD, score: blurScore };

      URL.revokeObjectURL(url);

      const result: QualityCheck = {
        passed: fileSizeCheck.passed && dimensionsCheck.passed && blurCheck.passed,
        blur: blurCheck,
        dimensions: dimensionsCheck,
        fileSize: fileSizeCheck,
      };

      resolve(result);
    };

    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve({
        passed: false,
        blur: { passed: false, score: 0 },
        dimensions: { passed: false, width: 0, height: 0 },
        fileSize: fileSizeCheck,
      });
    };

    img.src = url;
  });
}

export function getQualityMessage(check: QualityCheck): string | null {
  if (check.passed) return null;

  if (!check.fileSize.passed) {
    if (check.fileSize.bytes < MIN_FILE_SIZE)
      return "Image file is too small. Try a higher quality photo.";
    return "Image file is too large (max 10MB). Try a lower resolution.";
  }

  if (!check.dimensions.passed) {
    return "Image resolution is too low. Try getting closer to the document.";
  }

  if (!check.blur.passed) {
    return "Tip: For best results, hold steady and use good lighting.";
  }

  return "Image quality check failed. Try taking another photo.";
}
