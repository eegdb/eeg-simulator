"""MNE-based coupling model using source space distances and anatomical information

Provides coupling calculation methods based on MNE source space data:
1. Inter-patch coupling: anatomical weight x distance decay + KNN sparse connection
2. Intra-patch coupling: distance coupling between dipoles
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from scipy.spatial import cKDTree
import mne


class MNECouplingCalculator:
    """MNE coupling calculator based on source space geometry and anatomy
    
    Uses MNE source space data to compute distances between source points
    and calculates coupling weights with anatomical labels.
    """
    
    def __init__(self, src: mne.SourceSpaces, labels: Dict[str, Dict] = None):
        """
        Args:
            src: MNE source space object
            labels: Anatomical labels dict {hemi: {label_name: vertices}}
        """
        self.src = src
        self.labels = labels or {}
        
        # Build vertex coordinate mapping
        self._build_vertex_coords()
        
        # Build anatomical label mapping
        self._build_label_mapping()
        
    def _build_vertex_coords(self):
        """Build vertex coordinate lookup table"""
        self.vertex_coords = {'lh': {}, 'rh': {}}
        self.all_coords = []
        self.all_vertices = []
        
        for src_idx, s in enumerate(self.src):
            if s['type'] == 'surf':
                hemi = 'lh' if src_idx == 0 else 'rh'
                rr = s['rr']  # Vertex coordinates (N x 3)
                vertno = s['vertno']  # Actually used vertex indices
                
                for i, v in enumerate(vertno):
                    self.vertex_coords[hemi][v] = rr[v]
                    self.all_coords.append(rr[v])
                    self.all_vertices.append((hemi, v))
        
        self.all_coords = np.array(self.all_coords)
        
        # Build KDTree for fast nearest neighbor queries
        if len(self.all_coords) > 0:
            self.kdtree = cKDTree(self.all_coords)
        else:
            self.kdtree = None
    
    def _build_label_mapping(self):
        """Build vertex to anatomical label mapping"""
        self.vertex_to_labels = {'lh': {}, 'rh': {}}
        
        for hemi in ['lh', 'rh']:
            hemi_labels = self.labels.get(hemi, {})
            for label_name, vertices in hemi_labels.items():
                for v in vertices:
                    if v not in self.vertex_to_labels[hemi]:
                        self.vertex_to_labels[hemi][v] = []
                    self.vertex_to_labels[hemi][v].append(label_name)
    
    def get_vertex_coord(self, hemi: str, vertno: int) -> Optional[np.ndarray]:
        """Get vertex coordinates
        
        Args:
            hemi: Hemisphere ('lh' or 'rh')
            vertno: Vertex number
            
        Returns:
            3D coordinate array or None
        """
        return self.vertex_coords.get(hemi, {}).get(vertno)
    
    def compute_distance(self, hemi1: str, vertno1: int, 
                         hemi2: str, vertno2: int) -> float:
        """Compute distance between two vertices
        
        Args:
            hemi1: First vertex hemisphere
            vertno1: First vertex number
            hemi2: Second vertex hemisphere
            vertno2: Second vertex number
            
        Returns:
            Euclidean distance (meters)
        """
        coord1 = self.get_vertex_coord(hemi1, vertno1)
        coord2 = self.get_vertex_coord(hemi2, vertno2)
        
        if coord1 is None or coord2 is None:
            return np.inf
        
        return np.linalg.norm(coord1 - coord2)
    
    def compute_anatomical_weight(self, hemi1: str, vertno1: int,
                                   hemi2: str, vertno2: int) -> float:
        """Compute anatomical weight
        
        If two vertices belong to the same anatomical label, weight = 1.0
        If different labels but same hemisphere, weight = 0.5
        If different hemispheres, weight = 0.3
        
        Args:
            hemi1, vertno1: First vertex
            hemi2, vertno2: Second vertex
            
        Returns:
            Anatomical weight (0-1)
        """
        # Different hemispheres, lower base weight
        if hemi1 != hemi2:
            return 0.3
        
        labels1 = set(self.vertex_to_labels.get(hemi1, {}).get(vertno1, []))
        labels2 = set(self.vertex_to_labels.get(hemi2, {}).get(vertno2, []))
        
        # Share anatomical labels
        if labels1 and labels2 and (labels1 & labels2):
            return 1.0
        
        # Same hemisphere but no shared labels
        return 0.5
    
    def compute_distance_decay(self, distance: float, 
                                decay_length: float = 0.02) -> float:
        """Compute distance decay factor
        
        Uses exponential decay: exp(-distance / decay_length)
        
        Args:
            distance: Distance (meters)
            decay_length: Decay length (meters), default 2cm
            
        Returns:
            Decay factor (0-1)
        """
        return np.exp(-distance / decay_length)
    
    def compute_patch_inter_coupling(self, patch1_centers: List[Tuple[str, int]],
                                      patch2_centers: List[Tuple[str, int]],
                                      k: int = 3,
                                      decay_length: float = 0.02) -> float:
        """Compute coupling strength between two patches
        
        Uses KNN sparse connection + anatomical weight x distance decay
        
        Args:
            patch1_centers: Patch1 center points list [(hemi, vertno), ...]
            patch2_centers: Patch2 center points list [(hemi, vertno), ...]
            k: KNN k value
            decay_length: Distance decay length (meters)
            
        Returns:
            Coupling strength (0-1)
        """
        if not patch1_centers or not patch2_centers:
            return 0.0
        
        couplings = []
        
        # Compute distances and weights for all center point pairs
        for h1, v1 in patch1_centers:
            for h2, v2 in patch2_centers:
                dist = self.compute_distance(h1, v1, h2, v2)
                if dist == np.inf:
                    continue
                
                # Anatomical weight
                anatomical_weight = self.compute_anatomical_weight(h1, v1, h2, v2)
                
                # Distance decay
                distance_weight = self.compute_distance_decay(dist, decay_length)
                
                # Combined weight
                coupling_strength = anatomical_weight * distance_weight
                couplings.append((coupling_strength, dist))
        
        if not couplings:
            return 0.0
        
        # Sort by distance, take nearest k connections
        couplings.sort(key=lambda x: x[1])
        k = min(k, len(couplings))
        
        # Return average coupling strength
        return np.mean([c[0] for c in couplings[:k]])
    
    def compute_patch_intra_coupling(self, dipoles: List[Dict],
                                      decay_length: float = 0.01) -> np.ndarray:
        """Compute coupling matrix for dipoles within a patch
        
        Coupling based on distance between dipoles
        
        Args:
            dipoles: Dipole list, each containing 'hemi', 'vertno', 'position'
            decay_length: Distance decay length (meters)
            
        Returns:
            Coupling weight matrix (n_dipoles x n_dipoles)
        """
        n = len(dipoles)
        if n == 0:
            return np.array([])
        
        coupling_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i + 1, n):
                d1, d2 = dipoles[i], dipoles[j]
                
                # Get coordinates
                if 'position' in d1 and 'position' in d2:
                    pos1 = np.array(d1['position'])
                    pos2 = np.array(d2['position'])
                else:
                    # Get from source space
                    pos1 = self.get_vertex_coord(d1.get('hemi'), d1.get('vertno'))
                    pos2 = self.get_vertex_coord(d2.get('hemi'), d2.get('vertno'))
                
                if pos1 is None or pos2 is None:
                    continue
                
                # Compute distance and coupling weight
                dist = np.linalg.norm(pos1 - pos2)
                weight = self.compute_distance_decay(dist, decay_length)
                
                coupling_matrix[i, j] = weight
                coupling_matrix[j, i] = weight
        
        return coupling_matrix
    
    def find_k_nearest_neighbors(self, hemi: str, vertno: int, 
                                  k: int = 5) -> List[Tuple[str, int, float]]:
        """Find K nearest neighbor vertices
        
        Args:
            hemi: Target vertex hemisphere
            vertno: Target vertex number
            k: Number of neighbors
            
        Returns:
            [(hemi, vertno, distance), ...]
        """
        coord = self.get_vertex_coord(hemi, vertno)
        if coord is None or self.kdtree is None:
            return []
        
        # Query KDTree
        distances, indices = self.kdtree.query(coord, k=k+1)  # +1 because includes self
        
        neighbors = []
        for dist, idx in zip(distances[1:], indices[1:]):  # Skip first (self)
            neighbor_hemi, neighbor_vertno = self.all_vertices[idx]
            neighbors.append((neighbor_hemi, neighbor_vertno, dist))
        
        return neighbors


class MNECouplingEngine:
    """MNE coupling engine - manages coupling calculations based on MNE source space
    
    Replaces the original simple coupling model with MNE geometry and anatomical info.
    """
    
    def __init__(self, src: mne.SourceSpaces = None, 
                 labels: Dict[str, Dict] = None,
                 sampling_rate: float = 1000):
        """
        Args:
            src: MNE source space
            labels: Anatomical labels
            sampling_rate: Sampling rate
        """
        self.sampling_rate = sampling_rate
        self.calculator = None
        
        if src is not None:
            self.calculator = MNECouplingCalculator(src, labels)
        
        # Store inter-patch coupling configs
        self.inter_patch_couplings: Dict[str, Dict] = {}
        
        # Intra-patch coupling matrix cache
        self.intra_patch_couplings: Dict[str, np.ndarray] = {}
    
    def set_source_space(self, src: mne.SourceSpaces, 
                         labels: Dict[str, Dict] = None):
        """Set source space"""
        self.calculator = MNECouplingCalculator(src, labels)
    
    def compute_inter_patch_coupling(self, patch1_id: str, patch2_id: str,
                                      patch1_data: Dict, patch2_data: Dict,
                                      k: int = 3,
                                      decay_length: float = 0.02) -> float:
        """Compute coupling strength between two patches
        
        Args:
            patch1_id: Patch1 ID
            patch2_id: Patch2 ID
            patch1_data: Patch1 data containing dipoles list
            patch2_data: Patch2 data containing dipoles list
            k: KNN parameter
            decay_length: Distance decay length
            
        Returns:
            Coupling strength
        """
        if self.calculator is None:
            return 0.0
        
        # Get center points
        centers1 = [(d['hemi'], d['vertno']) for d in patch1_data.get('dipoles', [])
                    if 'hemi' in d and 'vertno' in d]
        centers2 = [(d['hemi'], d['vertno']) for d in patch2_data.get('dipoles', [])
                    if 'hemi' in d and 'vertno' in d]
        
        if not centers1 or not centers2:
            return 0.0
        
        coupling = self.calculator.compute_patch_inter_coupling(
            centers1, centers2, k, decay_length
        )
        
        # Cache result
        coupling_id = f"{patch1_id}_{patch2_id}"
        self.inter_patch_couplings[coupling_id] = {
            'source': patch1_id,
            'target': patch2_id,
            'strength': coupling,
            'k': k,
            'decay_length': decay_length
        }
        
        return coupling
    
    def compute_intra_patch_coupling(self, patch_id: str, 
                                      dipoles: List[Dict],
                                      decay_length: float = 0.01) -> np.ndarray:
        """Compute intra-patch coupling matrix
        
        Args:
            patch_id: Patch ID
            dipoles: Dipole list
            decay_length: Distance decay length
            
        Returns:
            Coupling matrix
        """
        if self.calculator is None:
            return np.array([])
        
        coupling_matrix = self.calculator.compute_patch_intra_coupling(
            dipoles, decay_length
        )
        
        self.intra_patch_couplings[patch_id] = coupling_matrix
        
        return coupling_matrix
    
    def apply_intra_patch_coupling(self, patch_id: str, 
                                    signals: np.ndarray) -> np.ndarray:
        """Apply intra-patch coupling to signals
        
        Args:
            patch_id: Patch ID
            signals: Dipole signals array (n_dipoles, n_samples)
            
        Returns:
            Coupled signals
        """
        if patch_id not in self.intra_patch_couplings:
            return signals
        
        coupling_matrix = self.intra_patch_couplings[patch_id]
        
        if coupling_matrix.size == 0:
            return signals
        
        # Apply coupling: each dipole's signal is affected by other dipoles
        n_dipoles = signals.shape[0]
        coupled_signals = signals.copy()
        
        for i in range(n_dipoles):
            for j in range(n_dipoles):
                if i != j and coupling_matrix[i, j] > 0:
                    # Add coupling contribution
                    coupled_signals[i] += coupling_matrix[i, j] * signals[j] * 0.1
        
        return coupled_signals
