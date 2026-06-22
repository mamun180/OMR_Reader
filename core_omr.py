import cv2
import numpy as np
try:
    from pyzbar.pyzbar import decode
except Exception:
    def decode(image): return []
from corner_detector import CornerDetector

class OMREngine:
    def __init__(self):
        self.detector = CornerDetector()

    def rotate_image(self, image, angle):
        if angle == 0: return image
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos = np.abs(M[0, 0]); sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos)); new_h = int((h * cos) + (w * sin))
        M[0, 2] += (new_w / 2) - center[0]; M[1, 2] += (new_h / 2) - center[1]
        return cv2.warpAffine(image, M, (new_w, new_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    def get_bubble_stats(self, bubble_image, params):
        if bubble_image is None or bubble_image.size == 0: return 0, 0, 0.0
        
        # Apply the same initial transformations as the main processing
        processed_bubble = cv2.cvtColor(bubble_image, cv2.COLOR_BGR2GRAY) if len(bubble_image.shape) > 2 else bubble_image
        if params['contrast'] != 1.0 or params['brightness'] != 0:
            processed_bubble = cv2.convertScaleAbs(processed_bubble, alpha=params['contrast'], beta=params['brightness'])
        blur_k = params['blur'] * 2 + 1
        processed_bubble = cv2.GaussianBlur(processed_bubble, (blur_k, blur_k), 0)
        
        thresh = cv2.adaptiveThreshold(processed_bubble, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 11, int(params['adaptive_c']))
        
        pixel_count = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        fill_perc = (pixel_count / total_pixels) * 100 if total_pixels > 0 else 0
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour_area = 0
        if contours: c = max(contours, key=cv2.contourArea); contour_area = cv2.contourArea(c)
            
        return pixel_count, contour_area, fill_perc

    def _process_grid(self, roi_image, rows, cols, params):
        if roi_image is None or roi_image.size == 0: return [], []
        if rows == 0 or cols == 0: return [], []
        
        processed_roi = cv2.cvtColor(roi_image, cv2.COLOR_BGR2GRAY)
        if params['contrast'] != 1.0 or params['brightness'] != 0:
            processed_roi = cv2.convertScaleAbs(processed_roi, alpha=params['contrast'], beta=params['brightness'])
        if params['rotation'] != 0.0:
            processed_roi = self.rotate_image(processed_roi, params['rotation'])
        
        blur_k = params['blur'] * 2 + 1
        if blur_k > 1: processed_roi = cv2.GaussianBlur(processed_roi, (blur_k, blur_k), 0)
        
        thresh_roi = cv2.adaptiveThreshold(processed_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY_INV, 11, int(params['adaptive_c']))

        cell_h = thresh_roi.shape[0] / rows; cell_w = thresh_roi.shape[1] / cols
        metric_matrix, all_cell_coords = [], []
        for r in range(rows):
            row_metrics = []
            for c in range(cols):
                x1, y1 = int(c * cell_w), int(r * cell_h); x2, y2 = int((c + 1) * cell_w), int((r + 1) * cell_h)
                all_cell_coords.append((x1, y1, x2, y2))
                cell = thresh_roi[y1:y2, x1:x2]
                
                metric_value = 0
                if cell.size > 0:
                    if params['method'] == 'pixel_count':
                        # To make the metric comparable to contour area, let's use fill percentage.
                        non_zero = cv2.countNonZero(cell); total = cell.shape[0] * cell.shape[1]
                        metric_value = (non_zero / total) if total > 0 else 0
                    else: # 'contour'
                        contours, _ = cv2.findContours(cell, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        if contours:
                            contour_c = max(contours, key=cv2.contourArea)
                            total_area = cell.shape[0] * cell.shape[1]
                            metric_value = cv2.contourArea(contour_c) / total_area if total_area > 0 else 0
                row_metrics.append(metric_value)
            metric_matrix.append(row_metrics)
        return metric_matrix, all_cell_coords

    def order_points(self, pts):
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1); rect[0] = pts[np.argmin(s)]; rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1); rect[1] = pts[np.argmin(diff)]; rect[3] = pts[np.argmax(diff)]
        return rect

    def four_point_transform(self, image, pts, output_size=None):
        rect = self.order_points(pts); (tl, tr, br, bl) = rect
        if output_size: maxWidth, maxHeight = output_size
        else:
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2)); widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))
            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2)); heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))
        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst); warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        return warped, M

    def read_qr(self, image):
        decoded = decode(image)
        if decoded: return decoded[0].data.decode("utf-8")
        return None

    def find_best_match_key(self, image_path, answer_keys_dict):
        image = cv2.imread(image_path)
        if image is None: return None

        for key_name, key_data in answer_keys_dict.items():
            template = key_data.get('template')
            if not template: continue

            # Try to find corners for this template
            corners = self.detector.find_corners(image.copy(), template.get('corner_properties', {}))
            if corners is None: continue 

            # Attempt to warp the image based on this template
            try:
                template_corners = np.array(template.get('template_corners'), dtype="float32")
                box_points_relative = template.get('box_points_relative', [])
                if len(box_points_relative) != 4: continue

                tl_corner_template = template_corners[0]
                template_box_points_abs = np.array([[p['x'] + tl_corner_template[0], p['y'] + tl_corner_template[1]] for p in box_points_relative], dtype="float32")

                H, _ = cv2.findHomography(template_corners, corners)
                if H is None: continue

                new_box_points = cv2.perspectiveTransform(template_box_points_abs.reshape(-1, 1, 2), H)
                warped_image, _ = self.four_point_transform(image, new_box_points.reshape(4, 2))
                if warped_image is None: continue

                # Now, with the warped image, try to find identifiers, specifically QR codes
                identifier_rois = template.get('rois', []) 
                for roi_data in identifier_rois:
                    if roi_data.get('type') == 'qrcode':
                        x, y, w, h = roi_data['x'], roi_data['y'], roi_data['width'], roi_data['height']
                        
                        # Ensure ROI coordinates are within image bounds
                        x, y = max(0, x), max(0, y)
                        w, h = min(w, warped_image.shape[1] - x), min(h, warped_image.shape[0] - y)
                        
                        if w <= 0 or h <= 0: continue

                        qr_roi_image = warped_image[y:y+h, x:x+w]
                        qr_data = self.read_qr(qr_roi_image)
                        
                        # A very simple matching: if the QR data contains the key_name (without extension)
                        # or a predefined 'qr_match_string' if exists in key_data meta
                        key_filename_base = os.path.splitext(key_name)[0]
                        qr_match_string = key_data.get('qr_match_string', key_filename_base)

                        if qr_data and qr_match_string in qr_data:
                            return key_name
            except Exception:
                # Log error or simply continue to the next key
                pass 

        # If no strong match found, return None
        return None
