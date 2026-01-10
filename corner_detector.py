import cv2
import numpy as np
class CornerDetector:
    def _order_points(self, pts):
        """Sorts coordinates: top-left, top-right, bottom-right, bottom-left"""
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        return rect

    def _find_circles(self, image):
        """Finds four corner circles in an OMR sheet as a fallback."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.medianBlur(gray, 5)
        
        # Parameters for HoughCircles can be tuned
        circles = cv2.HoughCircles(
            blurred, 
            cv2.HOUGH_GRADIENT, 
            dp=1.2, 
            minDist=100, 
            param1=50, 
            param2=30, 
            minRadius=10, 
            maxRadius=50
        )
        
        if circles is not None:
            circles = np.round(circles[0, :]).astype("int")
            
            # If we find 4 or more, take the first 4. This assumes the 4 corner
            # circles are the most prominent ones.
            if len(circles) >= 4:
                # Get the points from the circle centers
                points = np.array([c[:2] for c in circles[:4]], dtype="float32")
                return self._order_points(points)
        
        return None

    def detect_anchors(self, image, anchor_properties):
        if image is None or not anchor_properties:
            return []

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        detected_anchors = []
        for c in contours:
            area = cv2.contourArea(c)
            if not (anchor_properties.get('area_min', 0) < area < anchor_properties.get('area_max', float('inf'))):
                continue

            perimeter = cv2.arcLength(c, True)
            if perimeter == 0: continue

            approx = cv2.approxPolyDP(c, 0.04 * perimeter, True)
            num_vertices = len(approx)
            if not (anchor_properties.get('num_vertices_min', 4) <= num_vertices <= anchor_properties.get('num_vertices_max', 4)):
                continue

            (x, y, w, h) = cv2.boundingRect(approx)
            aspect_ratio = w / float(h) if h > 0 else 0
            if not (anchor_properties.get('aspect_ratio_min', 0) < aspect_ratio < anchor_properties.get('aspect_ratio_max', float('inf'))):
                continue

            M = cv2.moments(c)
            if M["m00"] == 0: continue
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            detected_anchors.append((cX, cY))
        
        return detected_anchors

    def find_corners(self, image, learned_properties=None, template_corners=None, template_anchors=None, anchor_properties=None, template=None):
        """
        Finds the four corner markers in an OMR sheet.
        - If learned_properties are provided, it uses them to find markers by area.
        - If more than 4 markers are found and sufficient template data is provided,
          it uses a homography derived from anchor points to select the best corner matches.
        - Otherwise, it falls back to selecting the largest 4 markers or automatic detection.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                       cv2.THRESH_BINARY_INV, 11, 2)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        found_markers = []

        if learned_properties:
            # Workflow 1: Use learned properties
            area_min = learned_properties.get('area_min', 100)
            area_max = learned_properties.get('area_max', 5000)
            aspect_ratio_min = learned_properties.get('aspect_ratio_min', 0.8)
            aspect_ratio_max = learned_properties.get('aspect_ratio_max', 1.2)
            num_vertices = learned_properties.get('num_vertices', 4)


            for c in contours:
                area = cv2.contourArea(c)
                if area_min <= area <= area_max:
                    peri = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.04 * peri, True)
                    if len(approx) == num_vertices:
                        (x, y, w, h) = cv2.boundingRect(approx)
                        aspect_ratio = w / float(h)
                        if aspect_ratio_min <= aspect_ratio <= aspect_ratio_max:
                            M = cv2.moments(c)
                            if M["m00"] != 0:
                                cX = int(M["m10"] / M["m00"])
                                cY = int(M["m01"] / M["m00"])
                                found_markers.append(((cX, cY), area))
        else:
            # Workflow 2: Automatic detection (find squares)
            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.04 * peri, True)
                
                if len(approx) == 4:
                    (x, y, w, h) = cv2.boundingRect(approx)
                    aspect_ratio = w / float(h)
                    area = cv2.contourArea(c)
                    
                    # Default hardcoded values for automatic detection
                    if 100 <= area <= 5000 and 0.8 <= aspect_ratio <= 1.2:
                        M = cv2.moments(c)
                        if M["m00"] != 0:
                            cX = int(M["m10"] / M["m00"])
                            cY = int(M["m01"] / M["m00"])
                            found_markers.append(((cX, cY), area))

        # --- Post-detection processing ---
        found_markers = self._prune_corner_candidates(found_markers)

        if len(found_markers) >= 4:
            # New logic: Use anchors to find best corner matches
            if template is not None and template.get('corner_anchor_distances') and template_anchors and anchor_properties and len(found_markers) >= 4:
                print("DEBUG: Attempting corner detection using anchor distance signatures.")
                detected_anchors = self.detect_anchors(image, anchor_properties)
                corner_coords = [m[0] for m in found_markers]

                matched_corners = self._find_corners_by_distance_signature(corner_coords, detected_anchors, template)

                if matched_corners is not None:
                    # The corners from this method are already ordered if the template was saved correctly.
                    return matched_corners
                else:
                    print("DEBUG: Distance signature method failed. Falling back to original logic.")
            
            # Fallback to original logic if distance method is not applicable or fails
            if template_corners and template_anchors and anchor_properties and len(found_markers) > 4:
                detected_anchors = self.detect_anchors(image, anchor_properties)
                
                if len(detected_anchors) >= 4 and len(template_anchors) >= 4:
                    src_pts = np.array([[p['x'], p['y']] for p in template_anchors], dtype='float32')
                    dst_pts = np.array(detected_anchors, dtype='float32')

                    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

                    if M is not None:
                        template_corners_np = np.array(template_corners, dtype='float32').reshape(-1, 1, 2)
                        predicted_corners = cv2.perspectiveTransform(template_corners_np, M)
                        predicted_corners = predicted_corners.reshape(-1, 2)
                        
                        marker_coords = np.array([m[0] for m in found_markers])
                        
                        matched_markers = []
                        for p_corner in predicted_corners:
                            distances = np.linalg.norm(marker_coords - p_corner, axis=1)
                            closest_marker_idx = np.argmin(distances)
                            matched_markers.append(found_markers[closest_marker_idx])
                            marker_coords[closest_marker_idx] = np.inf
                        
                        found_markers = matched_markers
                        points = np.array([p[0] for p in found_markers], dtype="float32")
                        return self._order_points(points)

            # Fallback to original logic
            found_markers = sorted(found_markers, key=lambda item: item[1], reverse=True)[:4]
            points = np.array([p[0] for p in found_markers], dtype="float32")
            return self._order_points(points)
        
        elif not learned_properties:
            # Fallback to circle detection ONLY if we were in full automatic mode
            return self._find_circles(image)

        return None


    def _prune_corner_candidates(self, markers, num_to_keep_per_corner=2):
        if not markers:
            return []

        coords = np.array([m[0] for m in markers])
        
        if len(coords) <= num_to_keep_per_corner * 4:
            return markers

        min_x, min_y = np.min(coords, axis=0)
        max_x, max_y = np.max(coords, axis=0)

        corners_of_bbox = {
            'tl': np.array([min_x, min_y]),
            'tr': np.array([max_x, min_y]),
            'br': np.array([max_x, max_y]),
            'bl': np.array([min_x, max_y]),
        }

        pruned_indices = set()

        for corner_pos in corners_of_bbox.values():
            distances = np.linalg.norm(coords - corner_pos, axis=1)
            closest_indices = np.argsort(distances)[:num_to_keep_per_corner]
            for idx in closest_indices:
                pruned_indices.add(idx)
        
        pruned_markers = [markers[i] for i in pruned_indices]
        print(f"DEBUG: Pruned corner candidates from {len(markers)} to {len(pruned_markers)}.")
        return pruned_markers


    def _calculate_geometry_hash(self, points):
        # points must be an ordered 4x2 numpy array (TL, TR, BR, BL)
        # Returns ratios of distances to create a scale-and-rotation-invariant hash
        d = np.linalg.norm
        epsilon = 1e-6 # Avoid division by zero
        
        side_ab = d(points[0] - points[1])
        side_bc = d(points[1] - points[2])
        side_cd = d(points[2] - points[3])
        side_da = d(points[3] - points[0])
        diag_ac = d(points[0] - points[2])
        diag_bd = d(points[1] - points[3])

        hash_vector = [
            diag_ac / (diag_bd + epsilon),
            side_ab / (diag_ac + epsilon),
            side_bc / (diag_ac + epsilon),
            side_cd / (diag_ac + epsilon),
            side_da / (diag_ac + epsilon)
        ]
        return np.array(hash_vector)

    def find_corners_from_anchors(self, image, template_corners, anchor_properties):
        """
        Automatically finds the four corner anchors on a new image using a geometric hash
        to match the pattern of the template's corners.
        """
        import itertools

        if not template_corners or not anchor_properties:
            return None

        # 1. Calculate the geometric hash of the reference template corners
        ordered_template_corners = self._order_points(np.array(template_corners, dtype='float32'))
        template_hash = self._calculate_geometry_hash(ordered_template_corners)

        # 2. Detect all anchor candidates on the new image
        detected_anchors = self.detect_anchors(image, anchor_properties)
        
        num_detected = len(detected_anchors)
        print(f"DEBUG: Detected {num_detected} anchor candidates for matching.")
        if num_detected > 60:
            print("WARNING: Too many anchor candidates detected (>60). Aborting automatic alignment. Try creating a template with more specific anchor properties.")
            return None
        if num_detected < 4:
            return None

        # 3. Iterate through combinations of detected anchors to find the best match
        best_error = float('inf')
        best_corners = None
        detected_anchors_np = np.array(detected_anchors, dtype='float32')

        for candidate_points_tuple in itertools.combinations(detected_anchors_np, 4):
            candidate_points = np.array(candidate_points_tuple, dtype='float32')
            ordered_candidate = self._order_points(candidate_points)
            
            candidate_hash = self._calculate_geometry_hash(ordered_candidate)
            
            # Compare hashes using Sum of Squared Differences
            error = np.sum((template_hash - candidate_hash)**2)
            
            if error < best_error:
                best_error = error
                best_corners = ordered_candidate
        
        # 4. Check if the best match is good enough (heuristic threshold)
        # A small error indicates the quadrilateral shapes are very similar proportionally.
        if best_error < 0.05:
            print(f"Found a good match with error: {best_error}")
            return best_corners
        else:
            print(f"No good match found. Best error was: {best_error}")
            return None


    def find_corners_by_relative_vectors(self, image, template):
        import itertools
        # 1. Get data from template
        ref_anchors = template.get('relative_corner_anchors')
        vectors = template.get('relative_vectors')
        anchor_props = template.get('anchor_properties')
        corner_props = template.get('corner_properties')

        if not all([ref_anchors, vectors, anchor_props, corner_props]):
            return None

        # 2. Detect all anchor candidates on the new image
        detected_anchors = self.detect_anchors(image, anchor_props)
        if len(detected_anchors) < 4:
            return None
        
        # 3. Identify the 4 corner anchors by matching the quadrilateral shape
        ref_hash = self._calculate_geometry_hash(self._order_points(np.array([(p['x'], p['y']) for p in ref_anchors], dtype='float32')))
        
        best_error = float('inf')
        identified_anchors_ordered = None
        
        for candidate_points_tuple in itertools.combinations(detected_anchors, 4):
            candidate_points = np.array(candidate_points_tuple, dtype='float32')
            ordered_candidate = self._order_points(candidate_points)
            candidate_hash = self._calculate_geometry_hash(ordered_candidate)
            error = np.sum((ref_hash - candidate_hash)**2)
            
            if error < best_error:
                best_error = error
                identified_anchors_ordered = ordered_candidate

        # Heuristic threshold for a good geometric match
        if best_error > 0.05 or identified_anchors_ordered is None:
            print(f"DEBUG: Could not find a good match for the 4 corner anchors. Best error: {best_error}")
            return None

        # 4. Predict approximate corner locations
        predicted_corners = []
        for i in range(4):
            px = identified_anchors_ordered[i][0] + vectors[i]['x']
            py = identified_anchors_ordered[i][1] + vectors[i]['y']
            predicted_corners.append((px, py))

        # 5. Refine corner positions with a local search
        final_corners = []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        for p_corner in predicted_corners:
            search_size = 50 # 50x50 pixel search window
            x, y = int(p_corner[0]), int(p_corner[1])
            x1, y1 = max(0, x - search_size//2), max(0, y - search_size//2)
            x2, y2 = x1 + search_size, y1 + search_size
            roi = gray[y1:y2, x1:x2]

            if roi.size == 0: continue

            blurred = cv2.GaussianBlur(roi, (5, 5), 0)
            thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            best_marker_pos = None
            if contours:
                # Find the best contour within the ROI based on corner_props
                best_contour = max(contours, key=cv2.contourArea)
                M = cv2.moments(best_contour)
                if M["m00"] != 0:
                    # Coords are relative to ROI, so add top-left corner of ROI back
                    cX = int(M["m10"] / M["m00"]) + x1
                    cY = int(M["m01"] / M["m00"]) + y1
                    best_marker_pos = (cX, cY)

            # If local search finds something, use it. Otherwise, use the prediction.
            final_corners.append(best_marker_pos if best_marker_pos else p_corner)

        if len(final_corners) != 4:
            return None
            
        # The points should already be in order
        return np.array(final_corners, dtype="float32")



    def _find_corners_by_distance_signature(self, corner_candidates, anchor_candidates, template):
        ideal_dist_signatures = template.get('corner_anchor_distances')
        template_key_anchors = template.get('anchor_points')

        if not all([ideal_dist_signatures, template_key_anchors]):
            return None

        if len(anchor_candidates) != len(template_key_anchors):
            print(f"DEBUG: Anchor count mismatch. Template has {len(template_key_anchors)}, but detected {len(anchor_candidates)}. Cannot use distance method.")
            return None

        anchor_candidates.sort(key=lambda p: (p[1], p[0]))
        identified_key_anchors = anchor_candidates

        corner_scores = [[] for _ in range(len(corner_candidates))]

        for i, c_cand in enumerate(corner_candidates):
            measured_dists = [np.linalg.norm(np.array(c_cand) - np.array(a_cand)) for a_cand in identified_key_anchors]
            
            mean_dist = np.mean(measured_dists)
            if mean_dist == 0: continue
            norm_measured_dists = np.array(measured_dists) / mean_dist

            for j, ideal_dists in enumerate(ideal_dist_signatures):
                norm_ideal_dists = np.array(ideal_dists) / np.mean(ideal_dists)
                error = np.sum((norm_measured_dists - norm_ideal_dists)**2)
                corner_scores[i].append(error)
        
        assignments = []
        for cand_idx, scores in enumerate(corner_scores):
            if not scores: continue
            for corner_idx, error in enumerate(scores):
                assignments.append({'error': error, 'cand_idx': cand_idx, 'corner_idx': corner_idx})
        
        assignments.sort(key=lambda x: x['error'])
        
        final_corners = [None] * 4
        used_candidates = set()
        assigned_corners = set()
        
        for assign in assignments:
            cand_idx, corner_idx = assign['cand_idx'], assign['corner_idx']
            if cand_idx not in used_candidates and corner_idx not in assigned_corners:
                final_corners[corner_idx] = corner_candidates[cand_idx]
                used_candidates.add(cand_idx)
                assigned_corners.add(corner_idx)
                if len(used_candidates) == 4:
                    break
        
        if None in final_corners:
            print("DEBUG: Could not find a full set of 4 matching corners using distance signatures.")
            return None
            
        print(f"DEBUG: Successfully found 4 corners using distance signatures.")
        return np.array(final_corners, dtype="float32")

    def find_corners_by_individual_features(self, image, template):
        import itertools
        # 1. Get data from template
        learned_anchor_props = template.get('learned_anchor_props')
        learned_corner_props = template.get('learned_corner_props')
        relative_vectors = template.get('relative_vectors')
        learned_features_centers = template.get('learned_features_centers') # Load the reference centers

        if not all([learned_anchor_props, learned_corner_props, relative_vectors, learned_features_centers]):
            print("DEBUG: Template missing data for individual feature detection.")
            return None

        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # 2. Find the 4 Corner Anchors using their individual properties
        found_anchor_centers = [None] * 4
        
        for i in range(4):
            props = learned_anchor_props[i]
            best_match_center, _ = self._find_best_contour_match(img_gray, props)
            if best_match_center:
                found_anchor_centers[i] = best_match_center
        
        # 3. Handle missing anchors
        found_indices = [i for i, v in enumerate(found_anchor_centers) if v is not None]
        missing_indices = [i for i, v in enumerate(found_anchor_centers) if v is None]

        if len(found_indices) < 3:
            print("DEBUG: Found fewer than 3 corner anchors. Cannot proceed.")
            return None
        
        if len(found_indices) == 3:
            print("DEBUG: Found 3/4 anchors, predicting the 4th.")
            ref_centers = [c for i, c in enumerate(learned_features_centers[0:4]) if i in found_indices]
            found_centers = [c for c in found_anchor_centers if c is not None]
            
            # Use Affine Transform to predict the missing point
            src = np.array(ref_centers, dtype=np.float32)
            dst = np.array(found_centers, dtype=np.float32)
            
            try:
                if len(src) == 3 and len(dst) == 3:
                    M = cv2.getAffineTransform(src, dst)
                    missing_ref_point = learned_features_centers[missing_indices[0]]
                    predicted_point = np.dot(M, [missing_ref_point[0], missing_ref_point[1], 1])
                    found_anchor_centers[missing_indices[0]] = (predicted_point[0], predicted_point[1])
                    print(f"DEBUG: Predicted missing anchor at {predicted_point}")
                else:
                    raise cv2.error("Incorrect number of points for affine transform.")
            except cv2.error as e:
                print(f"DEBUG: Affine transform failed: {e}. Cannot predict missing anchor.")
                return None
        
        # 4. Predict approximate corner locations from a full set of 4 anchors
        predicted_corners = [None] * 4
        for i in range(4):
            anchor_center = found_anchor_centers[i]
            vector = relative_vectors[i]
            predicted_corners[i] = (anchor_center[0] + vector['x'], anchor_center[1] + vector['y'])

        # 5. Refine corner positions with local search
        final_corners = [None] * 4
        for i in range(4):
            p_corner = predicted_corners[i]
            props = learned_corner_props[i]
            
            search_size = 50
            x, y = int(p_corner[0]), int(p_corner[1])
            x1, y1 = max(0, x - search_size//2), max(0, y - search_size//2)
            roi_img = image[y1:y1+search_size, x1:x1+search_size]

            refined_center, _ = self._find_best_contour_match(roi_img, props, offset=(x1, y1))
            final_corners[i] = refined_center if refined_center else p_corner
            
        return np.array(final_corners, dtype="float32")

    def find_corners_by_heuristic(self, image, template):
        # 1. Load data from template
        ref_anchors = template.get('heuristic_key_anchors')
        anchor_props = template.get('anchor_properties')
        corner_props = template.get('corner_properties')

        if not all([ref_anchors, anchor_props, corner_props]):
            return None
        
        # 2. Find all anchor and corner candidates
        all_anchors = self.detect_anchors(image, anchor_props)
        all_corners = self._find_all_contours(image, corner_props)

        if len(all_anchors) < 4 or len(all_corners) < 4:
            return None

        # 3. Identify the 4 key anchors on the new image
        key_anchors_list = self._find_extreme_anchors(all_anchors)
        if not key_anchors_list:
            return None
        
        # Convert to numpy arrays for distance calculation
        key_anchors_np = np.array([(p['x'], p['y']) for p in key_anchors_list])
        all_corners_np = np.array(all_corners)

        # 4. For each key anchor, find the nearest corner candidate
        final_corners = []
        used_corner_indices = set()

        for i in range(4): # For each key anchor (TL, TR, BR, BL)
            key_anchor = key_anchors_np[i]
            
            min_dist = float('inf')
            best_corner_idx = -1
            
            distances = np.linalg.norm(all_corners_np - key_anchor, axis=1)
            
            # Find the closest corner that hasn't been used yet
            sorted_indices = np.argsort(distances)
            for corner_idx in sorted_indices:
                if corner_idx not in used_corner_indices:
                    best_corner_idx = corner_idx
                    break
            
            if best_corner_idx != -1:
                final_corners.append(all_corners_np[best_corner_idx])
                used_corner_indices.add(best_corner_idx)
            else:
                # This should not happen if there are enough corners, but as a fallback
                return None 

        if len(final_corners) != 4:
            return None

        # The final_corners are implicitly ordered by the order of key_anchors
        return np.array(final_corners, dtype="float32")

    def _find_extreme_anchors(self, anchors):
        if len(anchors) < 4:
            return None

        # Group anchors by Y-coordinate with a 2px tolerance
        anchors.sort(key=lambda p: p[1])
        y_groups = []
        if not anchors: return None
        
        current_group = [anchors[0]]
        for i in range(1, len(anchors)):
            # If current anchor is close to the last one, add to group
            if abs(anchors[i][1] - current_group[-1][1]) <= 2:
                current_group.append(anchors[i])
            else:
                # Otherwise, start a new group
                y_groups.append(current_group)
                current_group = [anchors[i]]
        y_groups.append(current_group)

        # Find the top and bottom lines that match the criteria
        top_line_anchors = None
        bottom_line_anchors = None
        min_dist = 500

        for group in y_groups:
            if len(group) >= 2:
                group_coords = np.array(group, dtype='float32')
                min_x_in_group = np.min(group_coords[:, 0])
                max_x_in_group = np.max(group_coords[:, 0])
                dist = max_x_in_group - min_x_in_group
                
                if dist >= min_dist:
                    # Find the actual anchors that correspond to min_x and max_x
                    anchors_on_line = []
                    for anchor in group:
                        if anchor[0] == min_x_in_group or anchor[0] == max_x_in_group:
                            anchors_on_line.append(anchor)
                    
                    if len(anchors_on_line) == 2: # Ensure we found exactly two distinct anchors for the line
                        top_line_anchors = anchors_on_line
                        break
        
        for group in reversed(y_groups):
            if len(group) >= 2:
                group_coords = np.array(group, dtype='float32')
                min_x_in_group = np.min(group_coords[:, 0])
                max_x_in_group = np.max(group_coords[:, 0])
                dist = max_x_in_group - min_x_in_group

                if dist >= min_dist:
                    anchors_on_line = []
                    for anchor in group:
                        if anchor[0] == min_x_in_group or anchor[0] == max_x_in_group:
                            anchors_on_line.append(anchor)
                    
                    if len(anchors_on_line) == 2: # Ensure we found exactly two distinct anchors for the line
                        # Ensure it's not the same as the top line if there's only one relevant line
                        if top_line_anchors and group[0][1] == top_line_anchors[0][1]:
                            continue
                        bottom_line_anchors = anchors_on_line
                        break
        
        if top_line_anchors and bottom_line_anchors:
            # Sort by X to identify left and right anchors
            top_line_anchors.sort(key=lambda p: p[0])
            bottom_line_anchors.sort(key=lambda p: p[0])
            
            tl_anchor = top_line_anchors[0]
            tr_anchor = top_line_anchors[1]
            bl_anchor = bottom_line_anchors[0]
            br_anchor = bottom_line_anchors[1]
            
            return [
                {'x': tl_anchor[0], 'y': tl_anchor[1]},
                {'x': tr_anchor[0], 'y': tr_anchor[1]},
                {'x': br_anchor[0], 'y': br_anchor[1]},
                {'x': bl_anchor[0], 'y': bl_anchor[1]}
            ]
        
        return None

    def _find_best_contour_match(self, image, props, offset=(0, 0)):
        if image is None or image.size == 0:
            return None, float('inf')

        if len(image.shape) == 3:
            img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = image

        blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_match_center = None
        best_match_error = float('inf')

        if not contours:
            return None, float('inf')

        for c in contours:
            area = cv2.contourArea(c)
            peri = cv2.arcLength(c, True)
            if peri == 0: continue
            approx = cv2.approxPolyDP(c, 0.04 * peri, True)
            (x_b, y_b, w_b, h_b) = cv2.boundingRect(approx)

            if w_b == 0 or h_b == 0: continue

            error = 0
            error += ((area - props['area']) / (props['area'] + 1e-6))**2
            error += ((peri - props['perimeter']) / (props['perimeter'] + 1e-6))**2
            error += (len(approx) - props['num_vertices'])**2
            error += ((w_b/h_b - props['aspect_ratio']) / (props['aspect_ratio'] + 1e-6))**2

            if error < best_match_error:
                M = cv2.moments(c)
                if M["m00"] != 0:
                    best_match_error = error
                    cX = int(M["m10"] / M["m00"]) + offset[0]
                    cY = int(M["m01"] / M["m00"]) + offset[1]
                    best_match_center = (cX, cY)
        
        return best_match_center, best_match_error


