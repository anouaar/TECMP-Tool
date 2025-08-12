#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TECMP Advanced Statistical Analyzer with Modern Data Science Visualizations
Enhanced with interactive plots, real-time updates, and trendy UI design
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from scipy import stats
from scipy.signal import find_peaks
from scipy.fft import fft, fftfreq
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import json
import csv
import math
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing as mp

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWebEngineWidgets import QWebEngineView

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TECMPStatisticalAnalyser")

# Modern color schemes
MODERN_COLORS = {
    'primary': '#6C5CE7',
    'secondary': '#00B894',
    'accent': '#FD79A8',
    'warning': '#FDCB6E',
    'danger': '#D63031',
    'success': '#00CEC9',
    'dark': '#2D3436',
    'light': '#DFE6E9'
}

# Gradient color schemes for visualizations
GRADIENT_SCHEMES = {
    'purple': ['#E0AAFF', '#C77DFF', '#9D4EDD', '#7209B7', '#560BAD'],
    'teal': ['#90E0EF', '#00B4D8', '#0077B6', '#023E8A', '#03045E'],
    'sunset': ['#FFCCD5', '#FFB5A7', '#FD9E8C', '#F8961E', '#F76F03'],
    'ocean': ['#CAF0F8', '#90E0EF', '#00B4D8', '#0077B6', '#03045E'],
    'neon': ['#FF006E', '#FB5607', '#FFBE0B', '#8338EC', '#3A86FF']
}

# TECMP Protocol Constants
TECMP_DATA_TYPES = {
    0x0002: 'CAN',
    0x0003: 'CAN-FD', 
    0x0004: 'LIN',
    0x0008: 'FlexRay',
    0x0010: 'UART/RS232',
    0x0020: 'Analog',
    0x0080: 'Ethernet'
}

# Statistical thresholds by protocol
PROTOCOL_THRESHOLDS = {
    'FlexRay': {'cv_max': 0.005, 'autocorr_min': 0.6, 'alpha': 0.001},
    'LIN': {'cv_max': 0.02, 'autocorr_min': 0.5, 'alpha': 0.01},
    'CAN': {'cv_max': 0.05, 'autocorr_min': 0.3, 'alpha': 0.01},
    'CAN-FD': {'cv_max': 0.05, 'autocorr_min': 0.3, 'alpha': 0.01},
    'Ethernet': {'cv_max': 0.10, 'autocorr_min': 0.2, 'alpha': 0.05},
    'UART/RS232': {'cv_max': 0.08, 'autocorr_min': 0.3, 'alpha': 0.01},
    'Analog': {'cv_max': 0.15, 'autocorr_min': 0.2, 'alpha': 0.05}
}


class ModernVisualizationWidget(QWidget):
    """Modern visualization widget with Plotly interactive charts"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Web engine for Plotly charts
        self.web_view = QWebEngineView()
        self.web_view.setMinimumHeight(400)
        layout.addWidget(self.web_view)
        
    def create_behavior_distribution(self, analysis_results):
        """Create interactive behavior distribution chart"""
        behaviors = {}
        for result in analysis_results.values():
            if 'error' not in result:
                behavior = result['classification']['behavior']
                behaviors[behavior] = behaviors.get(behavior, 0) + 1
        
        fig = go.Figure(data=[
            go.Pie(
                labels=list(behaviors.keys()),
                values=list(behaviors.values()),
                hole=0.4,
                marker=dict(
                    colors=GRADIENT_SCHEMES['neon'][:len(behaviors)],
                    line=dict(color='white', width=2)
                ),
                textfont=dict(size=14, color='white'),
                hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
            )
        ])
        
        fig.update_layout(
            title={
                'text': 'Behavior Classification Distribution',
                'font': {'size': 20, 'color': MODERN_COLORS['dark']}
            },
            showlegend=True,
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Arial", size=12),
            hoverlabel=dict(bgcolor="white", font_size=14)
        )
        
        return fig.to_html(include_plotlyjs='cdn')
    
    def create_timing_heatmap(self, analysis_results):
        """Create timing pattern heatmap"""
        protocols = []
        metrics = ['Mean', 'CV', 'Jitter', 'Quality Score']
        data = []
        
        for result in analysis_results.values():
            if 'error' not in result:
                protocols.append(result['protocol'])
                row = [
                    result['basic_stats']['mean'],
                    result['basic_stats']['cv'] * 100,
                    result['quality_metrics']['jitter_percentage'],
                    result['quality_metrics']['quality_score']
                ]
                data.append(row)
        
        if not data:
            return "<html><body><p>No data available</p></body></html>"
        
        # Normalize data for heatmap
        data_norm = np.array(data).T
        
        fig = go.Figure(data=go.Heatmap(
            z=data_norm,
            x=protocols,
            y=metrics,
            colorscale='Viridis',
            showscale=True,
            hovertemplate='Protocol: %{x}<br>Metric: %{y}<br>Value: %{z:.2f}<extra></extra>',
            colorbar=dict(
                title="Normalized Value",
                titleside="right",
                tickmode="linear",
                tick0=0,
                dtick=20
            )
        ))
        
        fig.update_layout(
            title='Protocol Timing Metrics Heatmap',
            xaxis_title='Protocol',
            yaxis_title='Metrics',
            height=400,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(240,240,240,0.3)',
            font=dict(family="Arial", size=12)
        )
        
        return fig.to_html(include_plotlyjs='cdn')
    
    def create_3d_scatter(self, analysis_results):
        """Create 3D scatter plot of timing characteristics"""
        data_points = []
        colors = []
        texts = []
        
        color_map = {'CYCLIQUE': '#00CEC9', 'SEQUENTIEL': '#D63031', 'MIXTE': '#FDCB6E'}
        
        for group_key, result in analysis_results.items():
            if 'error' not in result:
                data_points.append([
                    result['basic_stats']['mean'],
                    result['basic_stats']['cv'] * 100,
                    result['quality_metrics']['quality_score']
                ])
                behavior = result['classification']['behavior']
                colors.append(color_map.get(behavior, '#DFE6E9'))
                texts.append(f"{result['protocol']}<br>Behavior: {behavior}")
        
        if not data_points:
            return "<html><body><p>No data available</p></body></html>"
        
        data_array = np.array(data_points)
        
        fig = go.Figure(data=[go.Scatter3d(
            x=data_array[:, 0],
            y=data_array[:, 1],
            z=data_array[:, 2],
            mode='markers',
            marker=dict(
                size=12,
                color=colors,
                opacity=0.8,
                line=dict(width=1, color='white')
            ),
            text=texts,
            hovertemplate='%{text}<br>Mean: %{x:.2f} us<br>CV: %{y:.2f}%<br>Quality: %{z:.1f}<extra></extra>'
        )])
        
        fig.update_layout(
            title='3D Timing Characteristics Analysis',
            scene=dict(
                xaxis_title='Mean Time (us)',
                yaxis_title='CV (%)',
                zaxis_title='Quality Score',
                bgcolor='rgba(240,240,240,0.1)',
                xaxis=dict(gridcolor='rgba(200,200,200,0.3)'),
                yaxis=dict(gridcolor='rgba(200,200,200,0.3)'),
                zaxis=dict(gridcolor='rgba(200,200,200,0.3)')
            ),
            height=500,
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(family="Arial", size=12)
        )
        
        return fig.to_html(include_plotlyjs='cdn')
    
    def create_time_series_plot(self, timestamp_data):
        """Create interactive time series plot"""
        if not timestamp_data['groups']:
            return "<html><body><p>No timestamp data available</p></body></html>"
        
        fig = make_subplots(
            rows=len(timestamp_data['groups']),
            cols=1,
            shared_xaxes=True,
            subplot_titles=[f"Device {k[0]:02X} - Interface {k[1]:04X}" 
                          for k in timestamp_data['groups'].keys()]
        )
        
        row = 1
        for group_key, group_data in timestamp_data['groups'].items():
            timestamps = group_data['timestamps']
            if len(timestamps) > 1:
                # Calculate deltas
                deltas = []
                times = []
                for i in range(1, len(timestamps)):
                    delta = (timestamps[i] - timestamps[i-1]) / 1000  # Convert to microseconds
                    deltas.append(delta)
                    times.append(timestamps[i] / 1e9)  # Convert to seconds
                
                fig.add_trace(
                    go.Scatter(
                        x=times,
                        y=deltas,
                        mode='lines+markers',
                        name=f"D{group_key[0]:02X}-I{group_key[1]:04X}",
                        line=dict(width=2),
                        marker=dict(size=4),
                        hovertemplate='Time: %{x:.3f}s<br>Delta: %{y:.2f} us<extra></extra>'
                    ),
                    row=row, col=1
                )
            row += 1
        
        fig.update_layout(
            title='Time Series Analysis - Inter-Packet Deltas',
            height=200 * len(timestamp_data['groups']),
            showlegend=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(240,240,240,0.1)',
            font=dict(family="Arial", size=11),
            hovermode='x unified'
        )
        
        fig.update_xaxes(title_text="Time (s)", row=len(timestamp_data['groups']), col=1)
        for i in range(1, len(timestamp_data['groups']) + 1):
            fig.update_yaxes(title_text="Delta (us)", row=i, col=1)
        
        return fig.to_html(include_plotlyjs='cdn')
    
    def display_chart(self, html_content):
        """Display HTML chart in web view"""
        self.web_view.setHtml(html_content)


class StatisticalAnalyzer:
    """Optimized statistical analysis pipeline for TECMP timestamps with large trace support"""
    
    # Performance limits
    MAX_FFT_POINTS = 65536  # 2^16 points max for FFT
    MAX_NORMALITY_TEST_POINTS = 5000  # Shapiro-Wilk limit
    MAX_DBSCAN_POINTS = 10000  # DBSCAN performance threshold
    WINDOW_SIZE = 10000  # Window size for streaming analysis
    SAMPLE_RATE = 0.1  # Sampling rate for very large datasets
    
    def __init__(self):
        self.groups = {}
        self.results = {}
        
    def analyze_group(self, group_key: Tuple, timestamps_ns: List[int], 
                     data_type: int) -> Dict[str, Any]:
        """Optimized statistical analysis for timestamp groups with large trace support"""
        
        if len(timestamps_ns) < 10:
            return {'error': 'Insufficient data', 'n': len(timestamps_ns)}
            
        # Check if we need to sample for performance
        is_large_trace = len(timestamps_ns) > self.WINDOW_SIZE
        
        if is_large_trace:
            logger.info(f"Large trace detected ({len(timestamps_ns)} points). Using optimized analysis.")
            return self._analyze_large_group(group_key, timestamps_ns, data_type)
        
        # Standard analysis for smaller traces
        timestamps_sorted = sorted(timestamps_ns)
        deltas_us = []
        for i in range(1, len(timestamps_sorted)):
            delta = (timestamps_sorted[i] - timestamps_sorted[i-1]) / 1000
            deltas_us.append(delta)
            
        if len(deltas_us) < 3:
            return {'error': 'Insufficient deltas', 'n': len(deltas_us)}
            
        deltas = np.array(deltas_us)
        protocol = TECMP_DATA_TYPES.get(data_type, 'Unknown')
        thresholds = PROTOCOL_THRESHOLDS.get(protocol, PROTOCOL_THRESHOLDS['Ethernet'])
        
        # Phase 1: Basic Statistics
        basic_stats = self._calculate_basic_stats(deltas)
        
        # Phase 2: Statistical Tests
        test_results = self._perform_statistical_tests(deltas, thresholds)
        
        # Phase 3: Classification
        classification = self._classify_behavior(basic_stats, test_results, thresholds)
        
        # Phase 4: Outlier Detection
        outliers = self._detect_outliers(deltas, classification['behavior'])
        
        # Phase 5: Windowed Analysis
        windowed_analysis = self._windowed_analysis(deltas, 50)
        
        # Phase 6: Prediction
        prediction = self._predict_behavior(deltas, classification['behavior'])
        
        return {
            'group_key': group_key,
            'protocol': protocol,
            'n_samples': len(deltas),
            'basic_stats': basic_stats,
            'statistical_tests': test_results,
            'classification': classification,
            'outliers': outliers,
            'windowed_analysis': windowed_analysis,
            'prediction': prediction,
            'quality_metrics': self._calculate_quality_metrics(
                basic_stats, test_results, outliers)
        }
    
    def _analyze_large_group(self, group_key: Tuple, timestamps_ns: List[int], 
                            data_type: int) -> Dict[str, Any]:
        """Optimized analysis for large timestamp groups using windowing and sampling"""
        
        protocol = TECMP_DATA_TYPES.get(data_type, 'Unknown')
        thresholds = PROTOCOL_THRESHOLDS.get(protocol, PROTOCOL_THRESHOLDS['Ethernet'])
        
        # Sort timestamps once
        timestamps_sorted = sorted(timestamps_ns)
        n_total = len(timestamps_sorted)
        
        # Initialize aggregated statistics
        all_basic_stats = []
        all_test_results = []
        all_outlier_counts = []
        
        # Process in windows for memory efficiency
        window_size = self.WINDOW_SIZE
        n_windows = (n_total + window_size - 1) // window_size
        
        logger.info(f"Processing {n_windows} windows of size {window_size}")
        
        for window_idx in range(n_windows):
            start_idx = window_idx * window_size
            end_idx = min(start_idx + window_size + 1, n_total)  # +1 for overlap
            
            window_timestamps = timestamps_sorted[start_idx:end_idx]
            
            # Calculate deltas for this window
            window_deltas = []
            for i in range(1, len(window_timestamps)):
                delta = (window_timestamps[i] - window_timestamps[i-1]) / 1000  # to microseconds
                window_deltas.append(delta)
            
            if len(window_deltas) < 3:
                continue
                
            window_deltas = np.array(window_deltas)
            
            # Basic stats for this window
            window_stats = self._calculate_basic_stats(window_deltas)
            all_basic_stats.append(window_stats)
            
            # Sample for expensive tests
            sampled_deltas = self._smart_sample(window_deltas, self.MAX_NORMALITY_TEST_POINTS)
            
            # Statistical tests on sample
            window_tests = self._perform_statistical_tests_optimized(sampled_deltas, thresholds)
            all_test_results.append(window_tests)
            
            # Outlier detection on sample
            outliers_sample = self._detect_outliers_fast(sampled_deltas)
            all_outlier_counts.append(outliers_sample['percentage'])
        
        # Aggregate results from all windows
        aggregated_stats = self._aggregate_window_stats(all_basic_stats)
        aggregated_tests = self._aggregate_test_results(all_test_results)
        
        # Classification based on aggregated results
        classification = self._classify_behavior(aggregated_stats, aggregated_tests, thresholds)
        
        # Aggregated outlier percentage
        avg_outlier_percentage = np.mean(all_outlier_counts) if all_outlier_counts else 0
        outliers = {
            'method': 'windowed_sampling',
            'count': int(avg_outlier_percentage * n_total / 100),
            'percentage': avg_outlier_percentage,
            'indices': [],  # Too expensive for large traces
            'values': [],
            'threshold_low': None,
            'threshold_high': None
        }
        
        # Prediction based on last window
        if all_basic_stats:
            last_window_mean = all_basic_stats[-1]['mean']
            last_window_std = all_basic_stats[-1]['std']
            prediction = {
                'method': 'windowed_gaussian',
                'next_value_estimate': float(last_window_mean),
                'confidence_interval_95': [
                    float(last_window_mean - 1.96 * last_window_std),
                    float(last_window_mean + 1.96 * last_window_std)
                ],
                'prediction_accuracy': 'medium',
                'stability_forecast': 'stable' if aggregated_stats['cv'] < 0.1 else 'variable'
            }
        else:
            prediction = {'method': 'none', 'error': 'No windows processed'}
        
        return {
            'group_key': group_key,
            'protocol': protocol,
            'n_samples': n_total - 1,  # Number of deltas
            'processing_mode': 'optimized_windowed',
            'n_windows': n_windows,
            'basic_stats': aggregated_stats,
            'statistical_tests': aggregated_tests,
            'classification': classification,
            'outliers': outliers,
            'windowed_analysis': {'window_size': window_size, 'n_windows': n_windows},
            'prediction': prediction,
            'quality_metrics': self._calculate_quality_metrics(
                aggregated_stats, aggregated_tests, outliers)
        }
    
    def _smart_sample(self, data: np.ndarray, max_size: int) -> np.ndarray:
        """Intelligent sampling preserving distribution characteristics"""
        if len(data) <= max_size:
            return data
        
        # Stratified sampling to preserve distribution
        n_samples = min(max_size, len(data))
        
        # Include extremes
        percentiles = [0, 5, 25, 50, 75, 95, 100]
        stratified_indices = []
        
        for p in percentiles:
            idx = int(len(data) * p / 100)
            stratified_indices.append(min(idx, len(data) - 1))
        
        # Random sample for the rest
        remaining = n_samples - len(stratified_indices)
        if remaining > 0:
            random_indices = np.random.choice(
                len(data), size=remaining, replace=False
            )
            stratified_indices.extend(random_indices)
        
        return data[sorted(set(stratified_indices))]
    
    def _perform_statistical_tests_optimized(self, deltas: np.ndarray, 
                                            thresholds: Dict) -> Dict[str, Any]:
        """Optimized statistical tests for sampled data"""
        results = {}
        
        # Normality test on sample
        if len(deltas) <= self.MAX_NORMALITY_TEST_POINTS:
            stat, p_val = stats.shapiro(deltas)
            results['normality'] = {
                'test': 'shapiro_sampled',
                'statistic': float(stat),
                'p_value': float(p_val),
                'is_normal': p_val > thresholds['alpha'],
                'sample_size': len(deltas)
            }
        else:
            # Use Anderson-Darling for larger samples
            stat, critical_values, significance_level = stats.anderson(deltas)
            results['normality'] = {
                'test': 'anderson_sampled',
                'statistic': float(stat),
                'p_value': 0.05,
                'is_normal': stat < critical_values[2],
                'sample_size': len(deltas)
            }
        
        # Simplified autocorrelation
        if len(deltas) > 1:
            lag1_corr = np.corrcoef(deltas[:-1], deltas[1:])[0, 1]
            results['autocorrelation'] = {
                'test': 'lag1_correlation',
                'lag_1_corr': float(lag1_corr),
                'is_autocorrelated': abs(lag1_corr) > thresholds['autocorr_min']
            }
        else:
            results['autocorrelation'] = {'test': 'none', 'is_autocorrelated': False}
        
        # Optimized FFT
        fft_sample = self._smart_sample(deltas, self.MAX_FFT_POINTS)
        results['periodicity'] = self._fft_analysis_optimized(fft_sample)
        
        # Simple stationarity test
        results['stationarity'] = {'is_stationary': True, 'test': 'windowed'}
        
        return results
    
    def _fft_analysis_optimized(self, deltas: np.ndarray) -> Dict[str, Any]:
        """Optimized FFT for large datasets"""
        try:
            n = min(len(deltas), self.MAX_FFT_POINTS)
            n_fft = 2 ** int(np.ceil(np.log2(n)))
            
            # Sample if needed
            if len(deltas) > n:
                deltas = self._smart_sample(deltas, n)
            
            windowed = deltas * np.hanning(len(deltas))
            fft_vals = fft(windowed, n_fft)
            freqs = fftfreq(n_fft, d=np.mean(deltas))
            
            magnitudes = np.abs(fft_vals[:n_fft//2])
            pos_freqs = freqs[:n_fft//2]
            
            # Only find top peaks for performance
            peaks, properties = find_peaks(magnitudes, height=np.max(magnitudes)*0.1)
            
            if len(peaks) > 0:
                top_peaks = peaks[np.argsort(properties['peak_heights'])[-5:]]  # Top 5 peaks
                dominant_idx = top_peaks[np.argmax(magnitudes[top_peaks])]
                dominant_freq = pos_freqs[dominant_idx]
                dominant_mag = magnitudes[dominant_idx]
                
                noise_floor = np.median(magnitudes)  # Use median for robustness
                snr = dominant_mag / noise_floor if noise_floor > 0 else 0
                
                return {
                    'has_dominant_peak': True,
                    'dominant_frequency': float(dominant_freq),
                    'dominant_period': float(1/dominant_freq) if dominant_freq > 0 else 0,
                    'peak_magnitude': float(dominant_mag),
                    'snr': float(snr),
                    'is_periodic': snr > 3.0,
                    'fft_points': n
                }
            
            return {'has_dominant_peak': False, 'is_periodic': False, 'snr': 0.0}
            
        except Exception as e:
            logger.warning(f"FFT analysis failed: {e}")
            return {'error': 'FFT analysis failed', 'is_periodic': False}
    
    def _detect_outliers_fast(self, deltas: np.ndarray) -> Dict[str, Any]:
        """Fast outlier detection using IQR method"""
        q1, q3 = np.percentile(deltas, [25, 75])
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        outlier_mask = (deltas < lower_bound) | (deltas > upper_bound)
        outlier_count = np.sum(outlier_mask)
        
        return {
            'method': 'iqr_fast',
            'count': int(outlier_count),
            'percentage': float(outlier_count / len(deltas) * 100),
            'threshold_low': float(lower_bound),
            'threshold_high': float(upper_bound)
        }
    
    def _aggregate_window_stats(self, window_stats: List[Dict]) -> Dict[str, float]:
        """Aggregate statistics from multiple windows"""
        if not window_stats:
            return {}
        
        # Weighted average based on window sizes
        means = [s['mean'] for s in window_stats]
        stds = [s['std'] for s in window_stats]
        cvs = [s['cv'] for s in window_stats]
        
        return {
            'mean': float(np.mean(means)),
            'median': float(np.median(means)),
            'std': float(np.mean(stds)),
            'cv': float(np.mean(cvs)),
            'min': float(min(s['min'] for s in window_stats)),
            'max': float(max(s['max'] for s in window_stats)),
            'p5': float(np.percentile([s['p5'] for s in window_stats], 5)),
            'p95': float(np.percentile([s['p95'] for s in window_stats], 95)),
            'p99': float(np.percentile([s['p99'] for s in window_stats], 99)),
            'skewness': float(np.mean([s['skewness'] for s in window_stats])),
            'kurtosis': float(np.mean([s['kurtosis'] for s in window_stats]))
        }
    
    def _aggregate_test_results(self, test_results: List[Dict]) -> Dict[str, Any]:
        """Aggregate test results from multiple windows"""
        if not test_results:
            return {}
        
        # Majority voting for boolean results
        normality_votes = [r['normality']['is_normal'] for r in test_results if 'normality' in r]
        autocorr_votes = [r['autocorrelation']['is_autocorrelated'] for r in test_results if 'autocorrelation' in r]
        periodic_votes = [r['periodicity']['is_periodic'] for r in test_results if 'periodicity' in r]
        
        return {
            'normality': {
                'is_normal': sum(normality_votes) > len(normality_votes) / 2 if normality_votes else False,
                'confidence': sum(normality_votes) / len(normality_votes) if normality_votes else 0
            },
            'autocorrelation': {
                'is_autocorrelated': sum(autocorr_votes) > len(autocorr_votes) / 2 if autocorr_votes else False,
                'lag_1_corr': float(np.mean([r['autocorrelation'].get('lag_1_corr', 0) for r in test_results]))
            },
            'periodicity': {
                'is_periodic': sum(periodic_votes) > len(periodic_votes) / 2 if periodic_votes else False
            },
            'stationarity': {
                'is_stationary': True
            }
        }
    
    def _calculate_basic_stats(self, deltas: np.ndarray) -> Dict[str, float]:
        """Calculate basic statistical metrics"""
        return {
            'mean': float(np.mean(deltas)),
            'median': float(np.median(deltas)),
            'std': float(np.std(deltas)),
            'cv': float(np.std(deltas) / np.mean(deltas)) if np.mean(deltas) > 0 else 0,
            'min': float(np.min(deltas)),
            'max': float(np.max(deltas)),
            'p5': float(np.percentile(deltas, 5)),
            'p95': float(np.percentile(deltas, 95)),
            'p99': float(np.percentile(deltas, 99)),
            'skewness': float(stats.skew(deltas)),
            'kurtosis': float(stats.kurtosis(deltas))
        }
    
    def _perform_statistical_tests(self, deltas: np.ndarray, 
                                  thresholds: Dict) -> Dict[str, Any]:
        """Perform comprehensive statistical tests"""
        results = {}
        
        # Test 1: Normality
        if len(deltas) <= 5000:
            stat, p_val = stats.shapiro(deltas)
            results['normality'] = {
                'test': 'shapiro',
                'statistic': float(stat),
                'p_value': float(p_val),
                'is_normal': p_val > thresholds['alpha']
            }
        else:
            stat, p_val = stats.anderson(deltas)
            results['normality'] = {
                'test': 'anderson',
                'statistic': float(stat),
                'p_value': 0.05,
                'is_normal': stat < stat.critical_values[2]
            }
        
        # Test 2: Autocorrelation
        try:
            from statsmodels.stats.diagnostic import acorr_ljungbox
            lb_result = acorr_ljungbox(deltas, lags=min(10, len(deltas)//4), return_df=True)
            results['autocorrelation'] = {
                'test': 'ljung_box',
                'p_value': float(lb_result['lb_pvalue'].iloc[-1]),
                'is_autocorrelated': lb_result['lb_pvalue'].iloc[-1] < 0.05,
                'lag_1_corr': float(np.corrcoef(deltas[:-1], deltas[1:])[0,1])
            }
        except:
            lag1_corr = np.corrcoef(deltas[:-1], deltas[1:])[0,1]
            results['autocorrelation'] = {
                'test': 'simple_corr',
                'lag_1_corr': float(lag1_corr),
                'is_autocorrelated': abs(lag1_corr) > thresholds['autocorr_min']
            }
        
        # Test 3: Periodicity (FFT)
        fft_result = self._fft_analysis(deltas)
        results['periodicity'] = fft_result
        
        # Test 4: Stationarity
        results['stationarity'] = self._stationarity_test(deltas)
        
        return results
    
    def _fft_analysis(self, deltas: np.ndarray) -> Dict[str, Any]:
        """FFT-based periodicity analysis"""
        try:
            n = len(deltas)
            n_fft = 2 ** int(np.ceil(np.log2(n)))
            
            windowed = deltas * np.hanning(len(deltas))
            fft_vals = fft(windowed, n_fft)
            freqs = fftfreq(n_fft, d=np.mean(deltas))
            
            magnitudes = np.abs(fft_vals[:n_fft//2])
            pos_freqs = freqs[:n_fft//2]
            
            peaks, _ = find_peaks(magnitudes, height=np.max(magnitudes)*0.1)
            
            if len(peaks) > 0:
                dominant_idx = peaks[np.argmax(magnitudes[peaks])]
                dominant_freq = pos_freqs[dominant_idx]
                dominant_mag = magnitudes[dominant_idx]
                
                noise_floor = np.mean(magnitudes)
                snr = dominant_mag / noise_floor if noise_floor > 0 else 0
                
                return {
                    'has_dominant_peak': True,
                    'dominant_frequency': float(dominant_freq),
                    'dominant_period': float(1/dominant_freq) if dominant_freq > 0 else 0,
                    'peak_magnitude': float(dominant_mag),
                    'snr': float(snr),
                    'is_periodic': snr > 3.0
                }
            else:
                return {
                    'has_dominant_peak': False,
                    'is_periodic': False,
                    'snr': 0.0
                }
        except:
            return {'error': 'FFT analysis failed', 'is_periodic': False}
    
    def _stationarity_test(self, deltas: np.ndarray) -> Dict[str, Any]:
        """Simplified stationarity test"""
        try:
            n_chunks = min(5, len(deltas) // 10)
            if n_chunks < 2:
                return {'is_stationary': True, 'test': 'insufficient_data'}
                
            chunk_size = len(deltas) // n_chunks
            chunk_means = []
            
            for i in range(n_chunks):
                start = i * chunk_size
                end = start + chunk_size if i < n_chunks-1 else len(deltas)
                chunk_means.append(np.mean(deltas[start:end]))
            
            f_stat, p_val = stats.f_oneway(*[deltas[i*chunk_size:(i+1)*chunk_size] 
                                           for i in range(n_chunks-1)])
            
            return {
                'test': 'anova',
                'f_statistic': float(f_stat),
                'p_value': float(p_val),
                'is_stationary': p_val > 0.05
            }
        except:
            return {'error': 'Stationarity test failed', 'is_stationary': True}
    
    def _classify_behavior(self, basic_stats: Dict, test_results: Dict, 
                          thresholds: Dict) -> Dict[str, Any]:
        """Classify communication behavior"""
        
        cv_score = max(0, 1 - basic_stats['cv'] / thresholds['cv_max'])
        normality_score = 1.0 if test_results['normality']['is_normal'] else 0.0
        autocorr_score = 1.0 if test_results['autocorrelation'].get('is_autocorrelated', False) else 0.0
        periodicity_score = 1.0 if test_results['periodicity'].get('is_periodic', False) else 0.0
        
        combined_score = (0.25 * cv_score + 
                         0.25 * normality_score + 
                         0.25 * autocorr_score + 
                         0.25 * periodicity_score)
        
        if combined_score >= 0.9:
            behavior = 'CYCLIQUE'
            confidence = combined_score * 100
        elif combined_score >= 0.5:
            behavior = 'MIXTE'
            confidence = combined_score * 100
        else:
            behavior = 'SEQUENTIEL'
            confidence = (1 - combined_score) * 100
        
        return {
            'behavior': behavior,
            'confidence': confidence,
            'combined_score': combined_score,
            'individual_scores': {
                'cv': cv_score,
                'normality': normality_score,
                'autocorrelation': autocorr_score,
                'periodicity': periodicity_score
            }
        }
    
    def _detect_outliers(self, deltas: np.ndarray, behavior: str) -> Dict[str, Any]:
        """Adaptive outlier detection based on behavior"""
        outlier_indices = []
        outlier_values = []
        
        if behavior == 'CYCLIQUE':
            outlier_indices, outlier_values = self._grubbs_test(deltas, alpha=0.001)
        elif behavior == 'SEQUENTIEL':
            p1, p99 = np.percentile(deltas, [0.5, 99.5])
            outlier_mask = (deltas < p1) | (deltas > p99)
            outlier_indices = np.where(outlier_mask)[0].tolist()
            outlier_values = deltas[outlier_mask].tolist()
        else:  # MIXTE
            outlier_indices, outlier_values = self._iqr_dbscan_outliers(deltas)
        
        return {
            'method': behavior.lower(),
            'count': len(outlier_indices),
            'percentage': len(outlier_indices) / len(deltas) * 100,
            'indices': outlier_indices,
            'values': outlier_values,
            'threshold_low': float(np.min(outlier_values)) if outlier_values else None,
            'threshold_high': float(np.max(outlier_values)) if outlier_values else None
        }
    
    def _grubbs_test(self, data: np.ndarray, alpha: float = 0.001) -> Tuple[List[int], List[float]]:
        """Grubbs test for outliers"""
        outlier_indices = []
        outlier_values = []
        data_copy = data.copy()
        original_indices = list(range(len(data)))
        
        while len(data_copy) > 3:
            mean = np.mean(data_copy)
            std = np.std(data_copy, ddof=1)
            
            if std == 0:
                break
                
            abs_deviations = np.abs(data_copy - mean)
            max_idx = np.argmax(abs_deviations)
            g_stat = abs_deviations[max_idx] / std
            
            n = len(data_copy)
            t_crit = stats.t.ppf(1 - alpha/(2*n), n-2)
            g_crit = ((n-1) / np.sqrt(n)) * np.sqrt(t_crit**2 / (n-2 + t_crit**2))
            
            if g_stat > g_crit:
                outlier_indices.append(original_indices[max_idx])
                outlier_values.append(data_copy[max_idx])
                data_copy = np.delete(data_copy, max_idx)
                original_indices.pop(max_idx)
            else:
                break
                
        return outlier_indices, outlier_values
    
    def _iqr_dbscan_outliers(self, data: np.ndarray) -> Tuple[List[int], List[float]]:
        """IQR + DBSCAN outlier detection"""
        q1, q3 = np.percentile(data, [25, 75])
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        iqr_outliers = (data < lower_bound) | (data > upper_bound)
        
        if len(data) > 10:
            try:
                scaler = StandardScaler()
                data_scaled = scaler.fit_transform(data.reshape(-1, 1))
                
                clustering = DBSCAN(eps=0.5, min_samples=3).fit(data_scaled)
                cluster_outliers = clustering.labels_ == -1
                
                combined_outliers = iqr_outliers | cluster_outliers
            except:
                combined_outliers = iqr_outliers
        else:
            combined_outliers = iqr_outliers
        
        outlier_indices = np.where(combined_outliers)[0].tolist()
        outlier_values = data[combined_outliers].tolist()
        
        return outlier_indices, outlier_values
    
    def _windowed_analysis(self, deltas: np.ndarray, window_size: int) -> Dict[str, Any]:
        """Sliding window analysis for temporal changes"""
        if len(deltas) < window_size * 2:
            return {'error': 'Insufficient data for windowing'}
        
        window_results = []
        step_size = max(1, window_size // 2)
        
        for start in range(0, len(deltas) - window_size + 1, step_size):
            window_data = deltas[start:start + window_size]
            
            cv = np.std(window_data) / np.mean(window_data) if np.mean(window_data) > 0 else 0
            
            window_results.append({
                'start_idx': start,
                'mean': float(np.mean(window_data)),
                'cv': float(cv),
                'std': float(np.std(window_data))
            })
        
        cvs = [w['cv'] for w in window_results]
        means = [w['mean'] for w in window_results]
        
        return {
            'window_size': window_size,
            'n_windows': len(window_results),
            'windows': window_results,
            'cv_stability': float(np.std(cvs)),
            'mean_stability': float(np.std(means)),
            'is_stable': np.std(cvs) < 0.1 and np.std(means) < np.mean(means) * 0.2
        }
    
    def _predict_behavior(self, deltas: np.ndarray, behavior: str) -> Dict[str, Any]:
        """Predict future behavior based on current pattern"""
        
        if behavior == 'CYCLIQUE':
            mean_delta = np.mean(deltas)
            std_delta = np.std(deltas)
            
            ci_95_lower = mean_delta - 1.96 * std_delta
            ci_95_upper = mean_delta + 1.96 * std_delta
            
            return {
                'method': 'gaussian',
                'next_value_estimate': float(mean_delta),
                'confidence_interval_95': [float(ci_95_lower), float(ci_95_upper)],
                'prediction_accuracy': 'high' if std_delta/mean_delta < 0.1 else 'medium',
                'stability_forecast': 'stable'
            }
            
        elif behavior == 'SEQUENTIEL':
            p25, p75 = np.percentile(deltas, [25, 75])
            median = np.median(deltas)
            
            return {
                'method': 'quantile',
                'next_value_estimate': float(median),
                'likely_range': [float(p25), float(p75)],
                'prediction_accuracy': 'low',
                'stability_forecast': 'variable'
            }
            
        else:  # MIXTE
            hist, bins = np.histogram(deltas, bins=20)
            dominant_bin = np.argmax(hist)
            dominant_value = (bins[dominant_bin] + bins[dominant_bin + 1]) / 2
            
            return {
                'method': 'modal',
                'next_value_estimate': float(dominant_value),
                'dominant_mode': float(dominant_value),
                'prediction_accuracy': 'medium',
                'stability_forecast': 'mixed'
            }
    
    def _calculate_quality_metrics(self, basic_stats: Dict, test_results: Dict, 
                                  outliers: Dict) -> Dict[str, Any]:
        """Calculate communication quality metrics"""
        
        jitter = basic_stats['cv'] * 100
        
        cv_score = max(0, 100 - jitter * 10)
        outlier_score = max(0, 100 - outliers['percentage'] * 5)
        
        quality_score = (cv_score + outlier_score) / 2
        
        if quality_score >= 90:
            quality = 'EXCELLENT'
        elif quality_score >= 75:
            quality = 'GOOD'
        elif quality_score >= 50:
            quality = 'FAIR'
        else:
            quality = 'POOR'
        
        return {
            'jitter_percentage': jitter,
            'quality_score': quality_score,
            'quality_class': quality,
            'outlier_percentage': outliers['percentage'],
            'timing_stability': 'stable' if jitter < 5 else 'unstable'
        }


class TrafficAnalyserDialog(QDialog):
    """Advanced TECMP traffic analyser with modern visualizations"""
    
    def __init__(self, trace_manager, parent=None):
        super().__init__(parent)
        self.trace_manager = trace_manager
        self.setWindowTitle("TECMP Advanced Statistical Analyser - Modern Data Science Dashboard")
        self.setMinimumSize(1600, 950)
        
        # Modern dark theme
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
            }
            QTabWidget::pane {
                border: 2px solid #6C5CE7;
                background: rgba(255,255,255,0.95);
                border-radius: 10px;
            }
            QTabBar::tab {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #6C5CE7, stop:1 #9D4EDD);
                color: white;
                padding: 12px 20px;
                margin-right: 4px;
                border-radius: 8px 8px 0 0;
                font-weight: bold;
                font-size: 12px;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #00CEC9, stop:1 #00B894);
            }
            QPushButton {
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
                color: white;
                border: none;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QTableWidget {
                background-color: rgba(255,255,255,0.95);
                alternate-background-color: rgba(240,240,255,0.3);
                gridline-color: rgba(108,92,231,0.2);
                border: 2px solid #6C5CE7;
                border-radius: 8px;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QTextEdit {
                background: rgba(255,255,255,0.95);
                border: 2px solid #6C5CE7;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                color: white;
            }
        """)
        
        # Initialize components
        self.analyzer = StatisticalAnalyzer()
        self.visualization_widget = ModernVisualizationWidget()
        self.timestamp_data = self._extract_and_group_timestamps()
        self.analysis_results = {}
        
        self._setup_ui()
        self._perform_complete_analysis()
        self._update_visualizations()
    
    def _extract_and_group_timestamps(self) -> Dict[str, Any]:
        """Extract and group TECMP timestamps by (device_id, interface_id, data_type)"""
        groups = {}
        tecmp_timestamps = []
        
        for i, packet_info in enumerate(self.trace_manager.packet_infos):
            if 'TECMP' in packet_info.stack and packet_info.config and 'tecmp' in packet_info.config:
                tecmp_cfg = packet_info.config['tecmp']
                
                timestamp_ns = tecmp_cfg.get('timestamp')
                if timestamp_ns is not None:
                    device_id = tecmp_cfg.get('device_id', 0)
                    interface_id = tecmp_cfg.get('interface_id', 0)
                    data_type = tecmp_cfg.get('data_type_value', 0)
                    
                    group_key = (device_id, interface_id, data_type)
                    
                    if group_key not in groups:
                        groups[group_key] = {
                            'timestamps': [],
                            'device_id': device_id,
                            'interface_id': interface_id,
                            'data_type': data_type,
                            'protocol': TECMP_DATA_TYPES.get(data_type, 'Unknown'),
                            'counters': [],
                            'packet_indices': []
                        }
                    
                    groups[group_key]['timestamps'].append(timestamp_ns)
                    groups[group_key]['counters'].append(tecmp_cfg.get('counter', 0))
                    groups[group_key]['packet_indices'].append(i)
                    
                    tecmp_timestamps.append({
                        'index': i,
                        'timestamp_ns': timestamp_ns,
                        'device_id': device_id,
                        'interface_id': interface_id,
                        'data_type': data_type,
                        'counter': tecmp_cfg.get('counter', 0),
                        'group_key': group_key
                    })
        
        return {
            'groups': groups,
            'all_timestamps': tecmp_timestamps,
            'total_groups': len(groups),
            'total_tecmp_packets': len(tecmp_timestamps)
        }
    
    def _setup_ui(self):
        """Setup the modern statistical UI"""
        layout = QVBoxLayout(self)
        
        # Modern header with gradient
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6C5CE7, stop:0.5 #00CEC9, stop:1 #FD79A8);
                border-radius: 10px;
                padding: 15px;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        
        total_groups = self.timestamp_data['total_groups']
        total_tecmp = self.timestamp_data['total_tecmp_packets']
        total_packets = len(self.trace_manager.packet_infos)
        
        title_label = QLabel(
            f"?? TECMP Advanced Analytics Dashboard\n"
            f"?? {total_groups} Groups | ?? {total_tecmp} TECMP Packets | "
            f"?? {total_tecmp/total_packets*100:.1f}% Coverage"
        )
        title_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: white;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        """)
        header_layout.addWidget(title_label)
        
        # Real-time status indicator
        status_label = QLabel("? LIVE")
        status_label.setStyleSheet("""
            color: #00FF00;
            font-weight: bold;
            font-size: 14px;
            animation: blink 1s infinite;
        """)
        header_layout.addStretch()
        header_layout.addWidget(status_label)
        
        layout.addWidget(header_widget)
        
        # Create modern tab widget
        self.tabs = QTabWidget()
        
        # Dashboard tab with visualizations
        self.dashboard_tab = QWidget()
        self._setup_dashboard_tab()
        self.tabs.addTab(self.dashboard_tab, "?? Dashboard")
        
        # Statistical Analysis tab
        self.stats_analysis_tab = QWidget()
        self._setup_stats_analysis_tab()
        self.tabs.addTab(self.stats_analysis_tab, "?? Statistical Analysis")
        
        # Classification Results tab
        self.classification_tab = QWidget()
        self._setup_classification_tab()
        self.tabs.addTab(self.classification_tab, "?? Classification")
        
        # Prediction tab
        self.prediction_tab = QWidget()
        self._setup_prediction_tab()
        self.tabs.addTab(self.prediction_tab, "?? Predictions")
        
        # Quality Metrics tab
        self.quality_tab = QWidget()
        self._setup_quality_tab()
        self.tabs.addTab(self.quality_tab, "? Quality")
        
        layout.addWidget(self.tabs)
        
        # Modern button bar
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("?? Export Analysis")
        export_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #00CEC9, stop:1 #00B894);
        """)
        export_btn.clicked.connect(self._export_complete_analysis)
        
        refresh_btn = QPushButton("?? Refresh")
        refresh_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #6C5CE7, stop:1 #9D4EDD);
        """)
        refresh_btn.clicked.connect(self._refresh_complete_analysis)
        
        close_btn = QPushButton("? Close")
        close_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #D63031, stop:1 #74B9FF);
        """)
        close_btn.clicked.connect(self.accept)
        
        button_layout.addWidget(export_btn)
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _setup_dashboard_tab(self):
        """Setup modern dashboard with visualizations"""
        layout = QVBoxLayout(self.dashboard_tab)
        
        # Create splitter for multiple charts
        splitter = QSplitter(Qt.Vertical)
        
        # Add visualization widgets
        self.behavior_chart = ModernVisualizationWidget()
        self.heatmap_chart = ModernVisualizationWidget()
        self.scatter_3d_chart = ModernVisualizationWidget()
        self.time_series_chart = ModernVisualizationWidget()
        
        splitter.addWidget(self.behavior_chart)
        splitter.addWidget(self.heatmap_chart)
        splitter.addWidget(self.scatter_3d_chart)
        splitter.addWidget(self.time_series_chart)
        
        layout.addWidget(splitter)
    
    def _setup_stats_analysis_tab(self):
        """Setup statistical analysis results tab"""
        layout = QVBoxLayout(self.stats_analysis_tab)
        
        # Summary with modern styling
        self.stats_summary = QTextEdit()
        self.stats_summary.setReadOnly(True)
        self.stats_summary.setMaximumHeight(250)
        layout.addWidget(self.stats_summary)
        
        # Results table
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(15)
        self.stats_table.setHorizontalHeaderLabels([
            "Group", "Protocol", "N", "Mean (us)", "Std (us)", "CV (%)",
            "Normality p", "Autocorr", "Periodic", "Score", "Behavior",
            "Confidence", "Quality", "Outliers %", "Stability"
        ])
        self.stats_table.setSortingEnabled(True)
        self.stats_table.setAlternatingRowColors(True)
        layout.addWidget(self.stats_table)
    
    def _setup_classification_tab(self):
        """Setup classification results tab"""
        layout = QVBoxLayout(self.classification_tab)
        
        self.classification_summary = QTextEdit()
        self.classification_summary.setReadOnly(True)
        self.classification_summary.setMaximumHeight(200)
        layout.addWidget(self.classification_summary)
        
        self.classification_table = QTableWidget()
        self.classification_table.setColumnCount(10)
        self.classification_table.setHorizontalHeaderLabels([
            "Group", "Protocol", "Behavior", "Confidence (%)", "CV Score",
            "Normality Score", "Autocorr Score", "Periodic Score", "Combined Score", "Validation"
        ])
        self.classification_table.setSortingEnabled(True)
        self.classification_table.setAlternatingRowColors(True)
        layout.addWidget(self.classification_table)
    
    def _setup_prediction_tab(self):
        """Setup prediction results tab"""
        layout = QVBoxLayout(self.prediction_tab)
        
        self.prediction_summary = QTextEdit()
        self.prediction_summary.setReadOnly(True)
        self.prediction_summary.setMaximumHeight(200)
        layout.addWidget(self.prediction_summary)
        
        self.prediction_table = QTableWidget()
        self.prediction_table.setColumnCount(8)
        self.prediction_table.setHorizontalHeaderLabels([
            "Group", "Protocol", "Behavior", "Next Estimate (us)", "Confidence Range",
            "Method", "Accuracy", "Stability Forecast"
        ])
        self.prediction_table.setSortingEnabled(True)
        self.prediction_table.setAlternatingRowColors(True)
        layout.addWidget(self.prediction_table)
    
    def _setup_quality_tab(self):
        """Setup quality metrics tab"""
        layout = QVBoxLayout(self.quality_tab)
        
        self.quality_overview = QTextEdit()
        self.quality_overview.setReadOnly(True)
        self.quality_overview.setMaximumHeight(200)
        layout.addWidget(self.quality_overview)
        
        self.quality_table = QTableWidget()
        self.quality_table.setColumnCount(7)
        self.quality_table.setHorizontalHeaderLabels([
            "Group", "Protocol", "Quality Class", "Score", "Jitter (%)",
            "Timing Stability", "Recommendation"
        ])
        self.quality_table.setSortingEnabled(True)
        self.quality_table.setAlternatingRowColors(True)
        layout.addWidget(self.quality_table)
    
    def _perform_complete_analysis(self):
        """Perform complete statistical analysis with parallel processing for large traces"""
        logger.info("Starting complete statistical analysis...")
        
        # Progress dialog for large traces
        total_groups = len([g for g in self.timestamp_data['groups'].values() 
                           if len(g['timestamps']) >= 10])
        
        if total_groups == 0:
            logger.warning("No groups with sufficient data for analysis")
            return
        
        # Check if we need parallel processing
        total_timestamps = sum(len(g['timestamps']) for g in self.timestamp_data['groups'].values())
        use_parallel = total_timestamps > 100000 or total_groups > 10
        
        if use_parallel:
            logger.info(f"Using parallel processing for {total_groups} groups ({total_timestamps} total timestamps)")
            self._parallel_analysis(total_groups)
        else:
            # Sequential processing for smaller traces
            progress = QProgressDialog("Analyzing TECMP data...", "Cancel", 0, total_groups, self)
            progress.setWindowModality(Qt.WindowModal)
            progress.setMinimumDuration(0)
            
            analyzed = 0
            for group_key, group_data in self.timestamp_data['groups'].items():
                if progress.wasCanceled():
                    break
                    
                if len(group_data['timestamps']) >= 10:
                    progress.setLabelText(f"Analyzing {group_data['protocol']} - Group {analyzed+1}/{total_groups}")
                    progress.setValue(analyzed)
                    QApplication.processEvents()
                    
                    logger.info(f"Analyzing group {group_key}: {group_data['protocol']}")
                    
                    result = self.analyzer.analyze_group(
                        group_key, 
                        group_data['timestamps'], 
                        group_data['data_type']
                    )
                    
                    self.analysis_results[group_key] = result
                    analyzed += 1
            
            progress.setValue(total_groups)
        
        # Populate all UI components
        self._populate_stats_analysis()
        self._populate_classification_results()
        self._populate_prediction_results()
        self._populate_quality_metrics()
        
        logger.info(f"Analysis complete. {len(self.analysis_results)} groups analyzed.")
    
    def _parallel_analysis(self, total_groups: int):
        """Parallel analysis using ThreadPoolExecutor for I/O bound operations"""
        progress = QProgressDialog("Parallel TECMP Analysis...", "Cancel", 0, total_groups, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        
        # Determine optimal number of workers
        n_workers = min(mp.cpu_count(), 8, total_groups)
        logger.info(f"Using {n_workers} parallel workers")
        
        completed = 0
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            # Submit all analysis tasks
            future_to_group = {}
            
            for group_key, group_data in self.timestamp_data['groups'].items():
                if len(group_data['timestamps']) >= 10:
                    future = executor.submit(
                        self.analyzer.analyze_group,
                        group_key,
                        group_data['timestamps'],
                        group_data['data_type']
                    )
                    future_to_group[future] = group_key
            
            # Process completed futures
            for future in as_completed(future_to_group):
                if progress.wasCanceled():
                    executor.shutdown(wait=False)
                    break
                
                group_key = future_to_group[future]
                try:
                    result = future.result(timeout=30)
                    self.analysis_results[group_key] = result
                    completed += 1
                    
                    progress.setValue(completed)
                    progress.setLabelText(f"Completed {completed}/{total_groups} groups")
                    QApplication.processEvents()
                    
                except Exception as e:
                    logger.error(f"Analysis failed for group {group_key}: {e}")
                    self.analysis_results[group_key] = {'error': str(e)}
        
        progress.setValue(total_groups)
    
    def _update_visualizations(self):
        """Update all modern visualizations"""
        if self.analysis_results:
            # Behavior distribution pie chart
            html = self.behavior_chart.create_behavior_distribution(self.analysis_results)
            self.behavior_chart.display_chart(html)
            
            # Timing heatmap
            html = self.heatmap_chart.create_timing_heatmap(self.analysis_results)
            self.heatmap_chart.display_chart(html)
            
            # 3D scatter plot
            html = self.scatter_3d_chart.create_3d_scatter(self.analysis_results)
            self.scatter_3d_chart.display_chart(html)
            
            # Time series plot
            html = self.time_series_chart.create_time_series_plot(self.timestamp_data)
            self.time_series_chart.display_chart(html)
    
    def _populate_stats_analysis(self):
        """Populate statistical analysis tab"""
        total_analyzed = len(self.analysis_results)
        cyclique_count = sum(1 for r in self.analysis_results.values() 
                           if r.get('classification', {}).get('behavior') == 'CYCLIQUE')
        sequentiel_count = sum(1 for r in self.analysis_results.values() 
                              if r.get('classification', {}).get('behavior') == 'SEQUENTIEL')
        mixte_count = total_analyzed - cyclique_count - sequentiel_count
        
        summary_html = f"""
        <div style='font-family: Arial, sans-serif;'>
        <h2 style='color: #6C5CE7;'>?? Statistical Analysis Summary</h2>
        <hr style='border: 1px solid #6C5CE7;'>
        <ul style='font-size: 14px;'>
            <li><b>Total Groups Analyzed:</b> {total_analyzed}</li>
            <li><b style='color: #00CEC9;'>Cyclique:</b> {cyclique_count} ({cyclique_count/total_analyzed*100:.1f}%)</li>
            <li><b style='color: #D63031;'>Sequentiel:</b> {sequentiel_count} ({sequentiel_count/total_analyzed*100:.1f}%)</li>
            <li><b style='color: #FDCB6E;'>Mixte:</b> {mixte_count} ({mixte_count/total_analyzed*100:.1f}%)</li>
        </ul>
        </div>
        """
        self.stats_summary.setHtml(summary_html)
        
        # Populate table
        self.stats_table.setRowCount(len(self.analysis_results))
        row = 0
        
        for group_key, result in self.analysis_results.items():
            if 'error' in result:
                continue
                
            basic_stats = result['basic_stats']
            tests = result['statistical_tests']
            classification = result['classification']
            quality = result['quality_metrics']
            outliers = result['outliers']
            
            # Group identifier
            group_str = f"D{group_key[0]:02X}-I{group_key[1]:04X}-T{group_key[2]:02X}"
            self.stats_table.setItem(row, 0, QTableWidgetItem(group_str))
            
            # Protocol
            self.stats_table.setItem(row, 1, QTableWidgetItem(result['protocol']))
            
            # Sample size
            self.stats_table.setItem(row, 2, QTableWidgetItem(str(result['n_samples'])))
            
            # Basic stats
            self.stats_table.setItem(row, 3, QTableWidgetItem(f"{basic_stats['mean']:.2f}"))
            self.stats_table.setItem(row, 4, QTableWidgetItem(f"{basic_stats['std']:.2f}"))
            
            cv_item = QTableWidgetItem(f"{basic_stats['cv']*100:.2f}")
            if basic_stats['cv'] < 0.05:
                cv_item.setBackground(QBrush(QColor('#00CEC9')))
            elif basic_stats['cv'] > 0.2:
                cv_item.setBackground(QBrush(QColor('#D63031')))
            self.stats_table.setItem(row, 5, cv_item)
            
            # Statistical tests
            self.stats_table.setItem(row, 6, QTableWidgetItem(f"{tests['normality']['p_value']:.4f}"))
            self.stats_table.setItem(row, 7, QTableWidgetItem(f"{tests['autocorrelation'].get('lag_1_corr', 0):.3f}"))
            
            periodic_str = "Yes" if tests['periodicity'].get('is_periodic', False) else "No"
            self.stats_table.setItem(row, 8, QTableWidgetItem(periodic_str))
            
            # Classification
            self.stats_table.setItem(row, 9, QTableWidgetItem(f"{classification['combined_score']:.3f}"))
            
            behavior_item = QTableWidgetItem(classification['behavior'])
            if classification['behavior'] == 'CYCLIQUE':
                behavior_item.setBackground(QBrush(QColor('#00CEC9')))
            elif classification['behavior'] == 'SEQUENTIEL':
                behavior_item.setBackground(QBrush(QColor('#D63031')))
            else:
                behavior_item.setBackground(QBrush(QColor('#FDCB6E')))
            self.stats_table.setItem(row, 10, behavior_item)
            
            self.stats_table.setItem(row, 11, QTableWidgetItem(f"{classification['confidence']:.1f}"))
            
            # Quality
            quality_item = QTableWidgetItem(quality['quality_class'])
            color_map = {'EXCELLENT': '#00CEC9', 'GOOD': '#00B894', 'FAIR': '#FDCB6E', 'POOR': '#D63031'}
            quality_item.setBackground(QBrush(QColor(color_map.get(quality['quality_class'], '#FFFFFF'))))
            self.stats_table.setItem(row, 12, quality_item)
            
            self.stats_table.setItem(row, 13, QTableWidgetItem(f"{outliers['percentage']:.1f}"))
            self.stats_table.setItem(row, 14, QTableWidgetItem(quality['timing_stability']))
            
            row += 1
    
    def _populate_classification_results(self):
        """Populate classification results tab"""
        behaviors = {}
        confidences = []
        
        for result in self.analysis_results.values():
            if 'error' not in result:
                behavior = result['classification']['behavior']
                behaviors[behavior] = behaviors.get(behavior, 0) + 1
                confidences.append(result['classification']['confidence'])
        
        avg_confidence = np.mean(confidences) if confidences else 0
        
        summary_html = f"""
        <div style='font-family: Arial, sans-serif;'>
        <h3 style='color: #6C5CE7;'> Classification Results Summary</h3>
        <ul style='font-size: 14px;'>
            <li><b>Average Confidence:</b> {avg_confidence:.1f}%</li>
            <li><b style='color: #00CEC9;'>High Confidence (>90%):</b> {sum(1 for c in confidences if c > 90)} groups</li>
            <li><b style='color: #D63031;'>Low Confidence (<70%):</b> {sum(1 for c in confidences if c < 70)} groups</li>
        </ul>
        </div>
        """
        self.classification_summary.setHtml(summary_html)
        
        # Populate table (similar to original but with modern colors)
        self.classification_table.setRowCount(len(self.analysis_results))
        row = 0
        
        for group_key, result in self.analysis_results.items():
            if 'error' in result:
                continue
                
            classification = result['classification']
            scores = classification['individual_scores']
            
            group_str = f"D{group_key[0]:02X}-I{group_key[1]:04X}-T{group_key[2]:02X}"
            self.classification_table.setItem(row, 0, QTableWidgetItem(group_str))
            self.classification_table.setItem(row, 1, QTableWidgetItem(result['protocol']))
            
            behavior_item = QTableWidgetItem(classification['behavior'])
            if classification['behavior'] == 'CYCLIQUE':
                behavior_item.setBackground(QBrush(QColor('#00CEC9')))
            elif classification['behavior'] == 'SEQUENTIEL':
                behavior_item.setBackground(QBrush(QColor('#D63031')))
            else:
                behavior_item.setBackground(QBrush(QColor('#FDCB6E')))
            self.classification_table.setItem(row, 2, behavior_item)
            
            confidence_item = QTableWidgetItem(f"{classification['confidence']:.1f}")
            if classification['confidence'] > 90:
                confidence_item.setBackground(QBrush(QColor('#00CEC9')))
            elif classification['confidence'] < 70:
                confidence_item.setBackground(QBrush(QColor('#D63031')))
            self.classification_table.setItem(row, 3, confidence_item)
            
            self.classification_table.setItem(row, 4, QTableWidgetItem(f"{scores['cv']:.3f}"))
            self.classification_table.setItem(row, 5, QTableWidgetItem(f"{scores['normality']:.3f}"))
            self.classification_table.setItem(row, 6, QTableWidgetItem(f"{scores['autocorrelation']:.3f}"))
            self.classification_table.setItem(row, 7, QTableWidgetItem(f"{scores['periodicity']:.3f}"))
            self.classification_table.setItem(row, 8, QTableWidgetItem(f"{classification['combined_score']:.3f}"))
            
            windowed = result.get('windowed_analysis', {})
            validation = "STABLE" if windowed.get('is_stable', False) else "VARIABLE"
            self.classification_table.setItem(row, 9, QTableWidgetItem(validation))
            
            row += 1
    
    def _populate_prediction_results(self):
        """Populate prediction results tab"""
        methods = {}
        accuracies = {}
        
        for result in self.analysis_results.values():
            if 'error' not in result:
                prediction = result['prediction']
                method = prediction['method']
                accuracy = prediction['prediction_accuracy']
                
                methods[method] = methods.get(method, 0) + 1
                accuracies[accuracy] = accuracies.get(accuracy, 0) + 1
        
        summary_html = f"""
        <div style='font-family: Arial, sans-serif;'>
        <h3 style='color: #6C5CE7;'> Prediction Summary</h3>
        <ul style='font-size: 14px;'>
            <li><b>Prediction Methods:</b> {', '.join(f'{k}: {v}' for k, v in methods.items())}</li>
            <li><b>Accuracy Distribution:</b> {', '.join(f'{k}: {v}' for k, v in accuracies.items())}</li>
        </ul>
        </div>
        """
        self.prediction_summary.setHtml(summary_html)
        
        # Populate table
        self.prediction_table.setRowCount(len(self.analysis_results))
        row = 0
        
        for group_key, result in self.analysis_results.items():
            if 'error' in result:
                continue
                
            prediction = result['prediction']
            classification = result['classification']
            
            group_str = f"D{group_key[0]:02X}-I{group_key[1]:04X}-T{group_key[2]:02X}"
            self.prediction_table.setItem(row, 0, QTableWidgetItem(group_str))
            self.prediction_table.setItem(row, 1, QTableWidgetItem(result['protocol']))
            self.prediction_table.setItem(row, 2, QTableWidgetItem(classification['behavior']))
            
            self.prediction_table.setItem(row, 3, QTableWidgetItem(f"{prediction['next_value_estimate']:.2f}"))
            
            if 'confidence_interval_95' in prediction:
                ci = prediction['confidence_interval_95']
                range_str = f"[{ci[0]:.2f}, {ci[1]:.2f}]"
            elif 'likely_range' in prediction:
                lr = prediction['likely_range']
                range_str = f"[{lr[0]:.2f}, {lr[1]:.2f}]"
            else:
                range_str = "N/A"
            
            self.prediction_table.setItem(row, 4, QTableWidgetItem(range_str))
            self.prediction_table.setItem(row, 5, QTableWidgetItem(prediction['method']))
            
            accuracy_item = QTableWidgetItem(prediction['prediction_accuracy'])
            color_map = {'high': '#00CEC9', 'medium': '#FDCB6E', 'low': '#D63031'}
            accuracy_item.setBackground(QBrush(QColor(color_map.get(prediction['prediction_accuracy'], '#FFFFFF'))))
            self.prediction_table.setItem(row, 6, accuracy_item)
            
            self.prediction_table.setItem(row, 7, QTableWidgetItem(prediction['stability_forecast']))
            
            row += 1
    
    def _populate_quality_metrics(self):
        """Populate quality metrics tab"""
        quality_counts = {}
        jitters = []
        scores = []
        
        for result in self.analysis_results.values():
            if 'error' not in result:
                quality = result['quality_metrics']
                quality_class = quality['quality_class']
                quality_counts[quality_class] = quality_counts.get(quality_class, 0) + 1
                jitters.append(quality['jitter_percentage'])
                scores.append(quality['quality_score'])
        
        avg_jitter = np.mean(jitters) if jitters else 0
        avg_score = np.mean(scores) if scores else 0
        
        overview_html = f"""
        <div style='font-family: Arial, sans-serif;'>
        <h3 style='color: #6C5CE7;'>? Quality Metrics Overview</h3>
        <ul style='font-size: 14px;'>
            <li><b>Average Quality Score:</b> {avg_score:.1f}/100</li>
            <li><b>Average Jitter:</b> {avg_jitter:.2f}%</li>
            <li><b>Quality Distribution:</b> {', '.join(f'{k}: {v}' for k, v in quality_counts.items())}</li>
        </ul>
        </div>
        """
        self.quality_overview.setHtml(overview_html)
        
        # Populate table
        self.quality_table.setRowCount(len(self.analysis_results))
        row = 0
        
        for group_key, result in self.analysis_results.items():
            if 'error' in result:
                continue
                
            quality = result['quality_metrics']
            
            group_str = f"D{group_key[0]:02X}-I{group_key[1]:04X}-T{group_key[2]:02X}"
            self.quality_table.setItem(row, 0, QTableWidgetItem(group_str))
            self.quality_table.setItem(row, 1, QTableWidgetItem(result['protocol']))
            
            quality_item = QTableWidgetItem(quality['quality_class'])
            color_map = {'EXCELLENT': '#00CEC9', 'GOOD': '#00B894', 'FAIR': '#FDCB6E', 'POOR': '#D63031'}
            quality_item.setBackground(QBrush(QColor(color_map[quality['quality_class']])))
            self.quality_table.setItem(row, 2, quality_item)
            
            self.quality_table.setItem(row, 3, QTableWidgetItem(f"{quality['quality_score']:.1f}"))
            self.quality_table.setItem(row, 4, QTableWidgetItem(f"{quality['jitter_percentage']:.2f}"))
            self.quality_table.setItem(row, 5, QTableWidgetItem(quality['timing_stability']))
            
            if quality['quality_score'] >= 90:
                recommendation = "Optimal"
            elif quality['quality_score'] >= 75:
                recommendation = " Good"
            elif quality['quality_score'] >= 50:
                recommendation = "Monitor"
            else:
                recommendation = "Investigate"
            
            self.quality_table.setItem(row, 6, QTableWidgetItem(recommendation))
            
            row += 1
    
    def _export_complete_analysis(self):
        """Export complete statistical analysis"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Complete Analysis", 
            f"tecmp_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;CSV Files (*.csv);;Text Files (*.txt);;All Files (*.*)"
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    export_data = {
                        'analysis_metadata': {
                            'timestamp': datetime.now().isoformat(),
                            'total_packets': len(self.trace_manager.packet_infos),
                            'total_groups': len(self.analysis_results),
                            'analyzer_version': '2.0.0'
                        },
                        'group_results': {}
                    }
                    
                    for group_key, result in self.analysis_results.items():
                        group_id = f"device_{group_key[0]:04X}_interface_{group_key[1]:08X}_datatype_{group_key[2]:04X}"
                        export_data['group_results'][group_id] = result
                    
                    with open(filename, 'w') as f:
                        json.dump(export_data, f, indent=2, default=str)
                
                elif filename.endswith('.csv'):
                    with open(filename, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow([
                            'Group_ID', 'Protocol', 'Behavior', 'Confidence', 'Quality_Score',
                            'Jitter_Percent', 'Outliers_Percent', 'Prediction_Accuracy'
                        ])
                        
                        for group_key, result in self.analysis_results.items():
                            if 'error' not in result:
                                group_id = f"D{group_key[0]:02X}-I{group_key[1]:04X}-T{group_key[2]:02X}"
                                writer.writerow([
                                    group_id,
                                    result['protocol'],
                                    result['classification']['behavior'],
                                    f"{result['classification']['confidence']:.1f}",
                                    f"{result['quality_metrics']['quality_score']:.1f}",
                                    f"{result['quality_metrics']['jitter_percentage']:.2f}",
                                    f"{result['outliers']['percentage']:.1f}",
                                    result['prediction']['prediction_accuracy']
                                ])
                
                else:
                    with open(filename, 'w') as f:
                        f.write("TECMP Complete Statistical Analysis Report\n")
                        f.write("=" * 80 + "\n\n")
                        
                        total_groups = len(self.analysis_results)
                        behaviors = {}
                        for result in self.analysis_results.values():
                            if 'error' not in result:
                                behavior = result['classification']['behavior']
                                behaviors[behavior] = behaviors.get(behavior, 0) + 1
                        
                        f.write("SUMMARY\n")
                        f.write("-" * 40 + "\n")
                        f.write(f"Total Groups Analyzed: {total_groups}\n")
                        for behavior, count in behaviors.items():
                            f.write(f"{behavior}: {count} ({count/total_groups*100:.1f}%)\n")
                        f.write("\n")
                        
                        f.write("DETAILED RESULTS\n")
                        f.write("-" * 40 + "\n")
                        for group_key, result in self.analysis_results.items():
                            if 'error' not in result:
                                f.write(f"\nGroup: D{group_key[0]:02X}-I{group_key[1]:04X}-T{group_key[2]:02X}\n")
                                f.write(f"Protocol: {result['protocol']}\n")
                                f.write(f"Behavior: {result['classification']['behavior']}\n")
                                f.write(f"Confidence: {result['classification']['confidence']:.1f}%\n")
                                f.write(f"Quality: {result['quality_metrics']['quality_class']}\n")
                                f.write(f"Outliers: {result['outliers']['percentage']:.1f}%\n")
                                f.write(                                f"Next Prediction: {result['prediction']['next_value_estimate']:.2f} us\n")
                                f.write("-" * 40 + "\n")
                
                QMessageBox.information(self, "Export Success", 
                    f"Complete analysis exported to {filename}\n"
                    f"{len(self.analysis_results)} groups analyzed")
                
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
                logger.error(f"Export failed: {e}")
    
    def _refresh_complete_analysis(self):
        """Refresh complete analysis"""
        logger.info("Refreshing complete statistical analysis...")
        
        self.timestamp_data = self._extract_and_group_timestamps()
        self.analysis_results = {}
        
        self._perform_complete_analysis()
        self._update_visualizations()
        
        QMessageBox.information(self, "Analysis Refreshed", 
            f"Complete analysis refreshed\n"
            f"{len(self.analysis_results)} groups analyzed")


def main():
    """Test function for standalone execution"""
    import sys
    app = QApplication(sys.argv)
    
    class DummyTraceManager:
        def __init__(self):
            self.packets = []
            self.packet_infos = []
            self.trace_id = 12345
            
        def get_trace_statistics(self):
            return {
                'trace_id': self.trace_id,
                'packet_count': 0,
                'total_bytes': 0,
                'protocols': [],
                'start_time': None,
                'end_time': None
            }
    
    trace_manager = DummyTraceManager()
    dialog = TrafficAnalyserDialog(trace_manager)
    dialog.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()