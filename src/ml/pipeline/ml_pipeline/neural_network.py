import numpy as np
import pandas as pd
import json
import os
from typing import Dict, Any, Tuple
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score, precision_score, recall_score, f1_score
from sklearn.preprocessing import StandardScaler
from data_collector.preprocessor import DataPreprocessor
from logger.log_writer import Logger

class FeatureImportanceTracker:
    """Track feature importance during training"""
    
    def __init__(self, num_features: int):
        self.num_features = num_features
        self.importance_scores = np.zeros(num_features)
        self.update_count = 0
        
    def update(self, gradients: np.ndarray):
        """Update importance based on gradient magnitude"""
        # Handle both 1D gradients (biases) and 2D gradients (weights)
        if gradients.ndim == 2:
            # For weight gradients: aggregate across hidden units
            feature_importance = np.mean(np.abs(gradients), axis=1)
        else:
            # For 1D bias gradients
            feature_importance = np.abs(gradients).flatten()
        
        if len(feature_importance) == self.num_features:
            self.importance_scores += feature_importance
            self.update_count += 1
    
    def get_top_features(self, top_k: int = 10) -> Dict[int, float]:
        """Get top K important features"""
        if self.update_count == 0:
            return {}
        normalized = self.importance_scores / self.update_count
        top_indices = np.argsort(normalized)[-top_k:][::-1]
        return {int(idx): float(normalized[idx]) for idx in top_indices}
    
    def get_summary(self) -> Dict[str, Any]:
        """Get feature importance summary"""
        return {
            'total_features': self.num_features,
            'update_count': self.update_count,
            'top_features': self.get_top_features(),
            'avg_importance': float(np.mean(self.importance_scores) / max(self.update_count, 1))
        }

class AdaptiveLearningRate:
    """Adaptive learning rate scheduler"""
    
    def __init__(self, initial_lr: float = 0.001, strategy: str = 'cosine'):
        self.initial_lr = initial_lr
        self.strategy = strategy
        self.best_loss = float('inf')
        self.patience = 0
        
    def get_lr(self, epoch: int, current_loss: float = None) -> float:  # type: ignore
        """Get learning rate for current epoch"""
        if self.strategy == 'cosine':
            # Cosine annealing
            return self.initial_lr * (1 + np.cos(np.pi * epoch / 100)) / 2
        elif self.strategy == 'exponential':
            # Exponential decay
            return self.initial_lr * (0.95 ** epoch)
        elif self.strategy == 'adaptive':
            # Adapt based on loss improvement
            if current_loss is not None:
                if current_loss < self.best_loss:
                    self.best_loss = current_loss
                    self.patience = 0
                    return self.initial_lr  # Normal lr
                else:
                    self.patience += 1
                    return self.initial_lr * (0.5 ** (self.patience // 5))
            return self.initial_lr
        else:
            return self.initial_lr

class CustomNeuralNetwork:
    """Advanced custom neural network with modern deep learning features"""

    def __init__(self, input_dim, hidden_layers, output_dim, learning_rate=0.001,
                 dropout_rate=0.2, activation='leaky_relu', num_classes=3,
                 use_batch_norm=True, gradient_clip=1.0, lr_decay=0.995,
                 l2_lambda=0.001, use_attention=True, warmup_steps=100,
                 checkpoint_freq=50):
        self.input_dim = input_dim
        self.hidden_layers = hidden_layers
        self.output_dim = output_dim  # Use the provided output_dim parameter
        # For binary classification with output_dim=1, set num_classes=2
        # For multi-class, num_classes should equal output_dim or be explicitly provided
        if output_dim == 1:
            self.num_classes = 2  # Binary classification
        else:
            self.num_classes = output_dim if num_classes == 3 else num_classes
        self.learning_rate = learning_rate
        self.current_lr = learning_rate
        self.dropout_rate = dropout_rate
        self.activation = activation
        self.use_batch_norm = use_batch_norm
        self.gradient_clip = gradient_clip
        self.lr_decay = lr_decay
        self.l2_lambda = l2_lambda  # L2 regularization
        self.use_attention = use_attention
        self.warmup_steps = warmup_steps
        self.checkpoint_freq = checkpoint_freq
        
        # Advanced tracking features
        self.feature_importance = FeatureImportanceTracker(input_dim)
        self.adaptive_lr = AdaptiveLearningRate(learning_rate, strategy='adaptive')
        
        # Performance metrics tracking
        self.training_metrics = {
            'precision': [],
            'recall': [],
            'f1_score': [],
            'auc': []
        }

        # Initialize weights and biases
        self.weights = []
        self.biases = []
        self.batch_norm_params = []
        self.attention_weights = None
        self.initialize_weights()
        
        # Initialize batch normalization parameters after weights are created
        if self.use_batch_norm:
            for hidden_size in self.hidden_layers:
                self.batch_norm_params.append({
                    'gamma': np.ones((1, hidden_size)),
                    'beta': np.zeros((1, hidden_size)),
                    'running_mean': np.zeros((1, hidden_size)),
                    'running_var': np.ones((1, hidden_size))
                })
        
        # Initialize attention weights for last hidden layer
        if self.use_attention and len(self.hidden_layers) > 0:
            last_hidden_dim = self.hidden_layers[-1]
            self.attention_weights = np.random.randn(last_hidden_dim, last_hidden_dim) * np.sqrt(2 / last_hidden_dim)

        # Adam optimizer parameters
        self.beta1 = 0.9
        self.beta2 = 0.999
        self.epsilon = 1e-8
        self.m = [np.zeros_like(w) for w in self.weights]
        self.v = [np.zeros_like(w) for w in self.weights]
        self.t = 0

        # Checkpointing
        self.best_weights = None
        self.best_biases = None
        self.best_loss = float('inf')
        
        # Model scaling
        self.scaler = StandardScaler()

        self.is_trained = False



    def initialize_weights(self):
        """Initialize weights using Xavier initialization"""
        layer_dims = [self.input_dim] + self.hidden_layers + [self.output_dim]

        for i in range(len(layer_dims) - 1):
            # Xavier initialization
            w = np.random.randn(layer_dims[i], layer_dims[i+1]) * np.sqrt(2 / layer_dims[i])
            b = np.zeros((1, layer_dims[i+1]))

            self.weights.append(w)
            self.biases.append(b)

    def relu(self, x):
        """ReLU activation"""
        return np.maximum(0, x)

    def relu_derivative(self, x):
        """Derivative of ReLU"""
        return np.where(x > 0, 1, 0)

    def leaky_relu(self, x, alpha=0.01):
        """Leaky ReLU activation"""
        return np.where(x > 0, x, alpha * x)

    def leaky_relu_derivative(self, x, alpha=0.01):
        """Derivative of Leaky ReLU"""
        return np.where(x > 0, 1, alpha)

    def elu(self, x, alpha=1.0):
        """ELU activation"""
        return np.where(x > 0, x, alpha * (np.exp(x) - 1))

    def elu_derivative(self, x, alpha=1.0):
        """Derivative of ELU"""
        return np.where(x > 0, 1, alpha * np.exp(x))

    def swish(self, x):
        """Swish activation"""
        return x * self.sigmoid(x)

    def swish_derivative(self, x):
        """Derivative of Swish"""
        s = self.sigmoid(x)
        return s + x * s * (1 - s)

    def sigmoid(self, x):
        """Sigmoid activation for binary classification"""
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))

    def sigmoid_derivative(self, x):
        """Derivative of sigmoid"""
        s = self.sigmoid(x)
        return s * (1 - s)

    def softmax(self, x):
        """Softmax for multi-class classification"""
        exp_x = np.exp(x - np.max(x, axis=1, keepdims=True))
        return exp_x / np.sum(exp_x, axis=1, keepdims=True)

    def apply_activation(self, x, activation_type):
        """Apply specified activation function"""
        if activation_type == 'relu':
            return self.relu(x)
        elif activation_type == 'leaky_relu':
            return self.leaky_relu(x)
        elif activation_type == 'elu':
            return self.elu(x)
        elif activation_type == 'swish':
            return self.swish(x)
        elif activation_type == 'sigmoid':
            return self.sigmoid(x)
        elif activation_type == 'softmax':
            return self.softmax(x)
        else:
            return self.relu(x)  # default

    def activation_derivative(self, x, activation_type):
        """Derivative of activation function"""
        if activation_type == 'relu':
            return self.relu_derivative(x)
        elif activation_type == 'leaky_relu':
            return self.leaky_relu_derivative(x)
        elif activation_type == 'elu':
            return self.elu_derivative(x)
        elif activation_type == 'swish':
            return self.swish_derivative(x)
        elif activation_type == 'sigmoid':
            return self.sigmoid_derivative(x)
        else:
            return self.relu_derivative(x)

    def dropout(self, x, training=True):
        """Apply dropout"""
        if not training or self.dropout_rate == 0:
            return x

        mask = np.random.rand(*x.shape) > self.dropout_rate
        return x * mask / (1 - self.dropout_rate)

    def batch_normalize(self, x, params, training=True):
        """Apply batch normalization"""
        if params is None or not training:
            # Use running statistics for inference
            return (x - params['running_mean']) / np.sqrt(params['running_var'] + self.epsilon) * params['gamma'] + params['beta']

        # Calculate batch statistics
        mu = np.mean(x, axis=0)
        var = np.var(x, axis=0)

        # Normalize
        x_norm = (x - mu) / np.sqrt(var + self.epsilon)

        # Scale and shift
        out = params['gamma'] * x_norm + params['beta']

        # Update running statistics
        momentum = 0.9
        params['running_mean'] = momentum * params['running_mean'] + (1 - momentum) * mu
        params['running_var'] = momentum * params['running_var'] + (1 - momentum) * var

        return out

    def forward(self, X, training=True):
        """Forward propagation with advanced features
        
        Args:
            X: Input features (batch_size, input_dim)
            training: Whether in training mode (for dropout, batch norm)
            
        Returns:
            Tuple of (activations, z_values) for all layers
            
        Raises:
            ValueError: If input shape is invalid
        """
        # Input validation
        if not isinstance(X, np.ndarray):
            raise ValueError(f"Expected numpy array, got {type(X)}")
        
        if X.ndim != 2:
            raise ValueError(f"Expected 2D array, got {X.ndim}D array with shape {X.shape}")
        
        if X.shape[1] != self.input_dim:
            raise ValueError(
                f"Input feature dimension mismatch. Expected {self.input_dim}, "
                f"got {X.shape[1]}"
            )
        
        # Check for NaN or Inf values
        if np.isnan(X).any() or np.isinf(X).any():
            raise ValueError("Input contains NaN or Inf values")
        
        activations = [X]
        z_values = []

        for i, (w, b) in enumerate(zip(self.weights[:-1], self.biases[:-1])):
            z = np.dot(activations[-1], w) + b
            z_values.append(z)

            # Batch normalization
            if self.use_batch_norm and self.batch_norm_params[i] is not None:
                z = self.batch_normalize(z, self.batch_norm_params[i], training)

            # Activation
            a = self.apply_activation(z, self.activation)
            a = self.dropout(a, training)
            activations.append(a)

        # Attention mechanism on last hidden layer
        if self.use_attention and self.attention_weights is not None:
            # Simple scaled dot-product attention
            # Compute attention scores
            attention_scores = np.dot(activations[-1], self.attention_weights)  # (batch, hidden_dim)
            attention_weights_normalized = self.softmax(attention_scores)  # (batch, hidden_dim)
            # Apply attention weights element-wise (not summing across features)
            attended = activations[-1] * attention_weights_normalized
            activations[-1] = attended

        # Output layer with softmax for multi-class
        z = np.dot(activations[-1], self.weights[-1]) + self.biases[-1]
        z_values.append(z)
        if self.num_classes == 2:
            a = self.sigmoid(z)
        else:
            a = self.softmax(z)
        activations.append(a)

        return activations, z_values

    def backward(self, X, y, activations, z_values):
        """Backward propagation with multi-class support"""
        m = X.shape[0]
        grads_w = [np.zeros_like(w) for w in self.weights]
        grads_b = [np.zeros_like(b) for b in self.biases]

        # Output layer
        if self.num_classes == 2:
            dz = activations[-1] - y  # Binary cross-entropy
        else:
            dz = activations[-1] - y  # Categorical cross-entropy with softmax

        grads_w[-1] = np.dot(activations[-2].T, dz) / m
        grads_b[-1] = np.sum(dz, axis=0, keepdims=True) / m

        # Hidden layers
        for i in reversed(range(len(self.weights) - 1)):
            dz = np.dot(dz, self.weights[i+1].T) * self.activation_derivative(z_values[i], self.activation)
            grads_w[i] = np.dot(activations[i].T, dz) / m
            grads_b[i] = np.sum(dz, axis=0, keepdims=True) / m

        # L2 regularization
        for i in range(len(grads_w)):
            grads_w[i] += self.l2_lambda * self.weights[i]

        # Gradient clipping
        for i in range(len(grads_w)):
            grads_w[i] = np.clip(grads_w[i], -self.gradient_clip, self.gradient_clip)
            grads_b[i] = np.clip(grads_b[i], -self.gradient_clip, self.gradient_clip)

        return grads_w, grads_b

    def update_parameters(self, grads_w, grads_b):
        """Update weights and biases using Adam optimizer"""
        self.t += 1

        for i in range(len(self.weights)):
            # Adam update
            self.m[i] = self.beta1 * self.m[i] + (1 - self.beta1) * grads_w[i]
            self.v[i] = self.beta2 * self.v[i] + (1 - self.beta2) * (grads_w[i] ** 2)

            m_hat = self.m[i] / (1 - self.beta1 ** self.t)
            v_hat = self.v[i] / (1 - self.beta2 ** self.t)

            self.weights[i] -= self.current_lr * m_hat / (np.sqrt(v_hat) + self.epsilon)
            self.biases[i] -= self.current_lr * grads_b[i]

        # Learning rate decay
        self.current_lr = self.learning_rate * (self.lr_decay ** (self.t // 100))

    def train(self, X, y, epochs=100, batch_size=32, validation_split=0.2, early_stopping=True, patience=10):
        """Train the neural network with multi-class support and adaptive learning"""
        # ✅ INPUT VALIDATION
        assert isinstance(X, np.ndarray), "X must be numpy array"
        assert isinstance(y, np.ndarray), "y must be numpy array"
        assert len(X) == len(y), "X and y length mismatch"
        assert X.ndim == 2, f"X must be 2D, got {X.ndim}D"
        assert not np.any(np.isnan(X)), "X contains NaN values"
        assert not np.any(np.isinf(X)), "X contains inf values"
        assert not np.any(np.isnan(y)), "y contains NaN values"
        
        if X.shape[1] != self.input_dim:
            raise ValueError(f"X has {X.shape[1]} features, expected {self.input_dim}")
        
        # Normalize input data
        X_normalized = self.scaler.fit_transform(X)
        
        X_train, X_val, y_train, y_val = train_test_split(
            X_normalized, y, test_size=validation_split, random_state=42, shuffle=False
        )

        # Convert labels to one-hot for multi-class
        if self.num_classes > 2:
            y_train = np.eye(self.num_classes)[y_train.flatten().astype(int)]
            y_val = np.eye(self.num_classes)[y_val.flatten().astype(int)]
        else:
            y_train = y_train.reshape(-1, 1)
            y_val = y_val.reshape(-1, 1)

        best_loss = float('inf')
        patience_counter = 0
        history = {
            'train_loss': [],
            'val_loss': [],
            'train_acc': [],
            'val_acc': [],
            'train_precision': [],
            'train_recall': [],
            'train_f1': [],
            'learning_rates': []
        }

        for epoch in range(epochs):
            # Adaptive learning rate with loss-aware adjustment
            current_loss = history['val_loss'][-1] if history['val_loss'] else float('inf')
            self.current_lr = self.adaptive_lr.get_lr(epoch, current_loss)
            history['learning_rates'].append(self.current_lr)
            
            # Learning rate warm-up
            if self.t < self.warmup_steps:
                self.current_lr = self.learning_rate * (self.t / self.warmup_steps)

            # Mini-batch training
            indices = np.arange(X_train.shape[0])
            np.random.shuffle(indices)

            epoch_loss = 0
            epoch_acc = 0
            epoch_precision = 0
            epoch_recall = 0

            for start_idx in range(0, X_train.shape[0], batch_size):
                end_idx = min(start_idx + batch_size, X_train.shape[0])
                batch_indices = indices[start_idx:end_idx]

                X_batch = X_train[batch_indices]
                y_batch = y_train[batch_indices]

                # Forward pass
                activations, z_values = self.forward(X_batch, training=True)

                # Compute loss
                predictions = activations[-1]
                if self.num_classes == 2:
                    loss = -np.mean(y_batch * np.log(predictions + 1e-8) + (1 - y_batch) * np.log(1 - predictions + 1e-8))
                else:
                    loss = -np.mean(np.sum(y_batch * np.log(predictions + 1e-8), axis=1))
                epoch_loss += loss

                # Accuracy and precision/recall
                if self.num_classes == 2:
                    pred_classes = (predictions > 0.5).astype(int).flatten()
                    true_classes = y_batch.flatten().astype(int)
                else:
                    pred_classes = np.argmax(predictions, axis=1)
                    true_classes = np.argmax(y_batch, axis=1)
                
                acc = np.mean(pred_classes == true_classes)
                epoch_acc += acc
                
                # Calculate precision and recall
                try:
                    prec = precision_score(true_classes, pred_classes, zero_division=0, average='weighted')
                    rec = recall_score(true_classes, pred_classes, zero_division=0, average='weighted')
                    epoch_precision += prec
                    epoch_recall += rec
                except:
                    epoch_precision += 0
                    epoch_recall += 0

                # Backward pass
                grads_w, grads_b = self.backward(X_batch, y_batch, activations, z_values)
                
                # Track feature importance
                if len(grads_w) > 0:
                    self.feature_importance.update(grads_w[0])

                # Update parameters
                self.update_parameters(grads_w, grads_b)

            # Average over batches
            num_batches = max(1, X_train.shape[0] // batch_size)
            epoch_loss /= num_batches
            epoch_acc /= num_batches
            epoch_precision /= num_batches
            epoch_recall /= num_batches
            epoch_f1 = 2 * (epoch_precision * epoch_recall) / (epoch_precision + epoch_recall + 1e-8)

            # Validation
            val_activations, _ = self.forward(X_val, training=False)
            val_predictions = val_activations[-1]
            if self.num_classes == 2:
                val_loss = -np.mean(y_val * np.log(val_predictions + 1e-8) + (1 - y_val) * np.log(1 - val_predictions + 1e-8))
                val_pred_classes = (val_predictions > 0.5).astype(int).flatten()
                val_true_classes = y_val.flatten().astype(int)
            else:
                val_loss = -np.mean(np.sum(y_val * np.log(val_predictions + 1e-8), axis=1))
                val_pred_classes = np.argmax(val_predictions, axis=1)
                val_true_classes = np.argmax(y_val, axis=1)
            val_acc = np.mean(val_pred_classes == val_true_classes)

            history['train_loss'].append(epoch_loss)
            history['val_loss'].append(val_loss)
            history['train_acc'].append(epoch_acc)
            history['val_acc'].append(val_acc)
            history['train_precision'].append(epoch_precision)
            history['train_recall'].append(epoch_recall)
            history['train_f1'].append(epoch_f1)

            # Checkpointing
            if epoch % self.checkpoint_freq == 0 and val_loss < self.best_loss:
                self.best_loss = val_loss
                self.best_weights = [w.copy() for w in self.weights]
                self.best_biases = [b.copy() for b in self.biases]
                print(f"💾 Checkpoint saved at epoch {epoch}")

            # Early stopping
            if early_stopping:
                if val_loss < best_loss:
                    best_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        print(f"🛑 Early stopping at epoch {epoch}")
                        # Restore best weights before returning
                        if self.best_weights is not None:
                            self.load_best_weights()
                        break

            if epoch % 10 == 0:
                print(f"Epoch {epoch}: Loss={epoch_loss:.4f} | Val Loss={val_loss:.4f} | "
                      f"Acc={epoch_acc:.4f} | F1={epoch_f1:.4f} | LR={self.current_lr:.6f}")

        self.is_trained = True
        
        # Store final metrics
        self.training_metrics['precision'].append(history['train_precision'][-1])
        self.training_metrics['recall'].append(history['train_recall'][-1])
        self.training_metrics['f1_score'].append(history['train_f1'][-1])
        
        # Return full history with metrics
        history['epochs_trained'] = len(history['train_loss'])
        history['feature_importance'] = self.feature_importance.get_summary()
        history['final_train_loss'] = history['train_loss'][-1]
        history['final_val_loss'] = history['val_loss'][-1]
        
        return history

    def load_best_weights(self):
        """Restore best weights from checkpointing"""
        if self.best_weights is not None and self.best_biases is not None:
            self.weights = [w.copy() for w in self.best_weights]
            self.biases = [b.copy() for b in self.best_biases]
            print(f"Restored best weights with loss: {self.best_loss:.4f}")
        else:
            print("No best weights available to restore")

    def get_model_insights(self) -> Dict[str, Any]:
        """Get detailed model insights including feature importance and metrics"""
        return {
            'architecture': {
                'input_dim': self.input_dim,
                'hidden_layers': self.hidden_layers,
                'output_dim': self.output_dim,
                'num_parameters': self._count_parameters()
            },
            'hyperparameters': {
                'learning_rate': self.learning_rate,
                'dropout_rate': self.dropout_rate,
                'activation': self.activation,
                'l2_lambda': self.l2_lambda,
                'use_batch_norm': self.use_batch_norm,
                'use_attention': self.use_attention
            },
            'training_metrics': self.training_metrics,
            'feature_importance': self.feature_importance.get_summary(),
            'is_trained': self.is_trained
        }
    
    def _count_parameters(self) -> int:
        """Count total number of parameters in the network"""
        total = 0
        for w, b in zip(self.weights, self.biases):
            total += w.size + b.size
        return total
    
    def predict_with_uncertainty(self, X, mc_samples: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions with uncertainty estimation using MC Dropout"""
        predictions = []
        for _ in range(mc_samples):
            activations, _ = self.forward(X, training=True)  # Keep dropout active
            predictions.append(activations[-1])
        
        predictions = np.array(predictions)
        mean_pred = np.mean(predictions, axis=0)
        uncertainty = np.std(predictions, axis=0)
        
        return mean_pred, uncertainty

    def predict(self, X):
        """Make predictions"""
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        activations, _ = self.forward(X, training=False)
        return (activations[-1] > 0.5).astype(int)

    def predict_proba(self, X, mc_samples=10):
        """Make probability predictions with uncertainty estimation"""
        if not self.is_trained:
            raise ValueError("Model not trained yet")

        # Monte Carlo dropout for uncertainty
        predictions = []
        for _ in range(mc_samples):
            activations, _ = self.forward(X, training=True)  # Keep dropout active
            predictions.append(activations[-1])

        predictions = np.array(predictions)
        mean_pred = np.mean(predictions, axis=0)
        uncertainty = np.std(predictions, axis=0)

        return mean_pred, uncertainty

class TradingNeuralNetwork:
    def __init__(self, input_dim, hidden_layers, output_dim, learning_rate=0.001):
        self.input_dim = input_dim
        self.hidden_layers = hidden_layers
        self.output_dim = output_dim
        self.learning_rate = learning_rate

        # Use custom neural network
        self.model = CustomNeuralNetwork(
            input_dim=input_dim,
            hidden_layers=hidden_layers,
            output_dim=output_dim,
            learning_rate=learning_rate
        )

        self.is_trained = False

    @classmethod
    def load_model(cls, filepath):
        """Load model from JSON file with full architecture restoration"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Model file {filepath} not found")
        
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Recreate model
            model = cls(
                input_dim=data['input_dim'],
                hidden_layers=data['hidden_layers'],
                output_dim=data['output_dim'],
                learning_rate=data.get('learning_rate', 0.001)
            )
            
            model.is_trained = data.get('is_trained', True)
            print(f"✅ Model loaded from {filepath}")
            print(f"   Architecture: {data['hidden_layers']}")
            print(f"   Trained: {model.is_trained}")
            
            return model
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            raise

    def save_model(self, filepath):
        """Save model to JSON file with complete metadata"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        data = {
            'input_dim': self.input_dim,
            'hidden_layers': self.hidden_layers,
            'output_dim': self.output_dim,
            'learning_rate': self.learning_rate,
            'is_trained': self.is_trained,
            'model_insights': self.get_model_insights(),
            'saved_at': datetime.now().isoformat(),
            'version': '2.0'
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"✅ Model saved to {filepath}")

    def get_model_insights(self) -> Dict[str, Any]:
        """Get full model insights"""
        return self.model.get_model_insights()

    def train(self, X, y, validation_split=0.2, epochs=100, batch_size=32, early_stopping=True):
        """Train the neural network"""
        # Convert y to proper shape for binary classification
        if y.ndim == 1:
            y = y.reshape(-1, 1)

        result = self.model.train(
            X, y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            early_stopping=early_stopping,
            patience=15
        )
        self.is_trained = True
        return result

    def predict(self, X):
        """Make predictions"""
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        return self.model.predict(X)
    
    def predict_with_uncertainty(self, X, mc_samples: int = 10) -> Tuple[np.ndarray, np.ndarray]:
        """Make predictions with uncertainty estimation"""
        return self.model.predict_with_uncertainty(X, mc_samples)

    def predict_proba(self, X):
        """Make probability predictions"""
        if not self.is_trained:
            raise ValueError("Model not trained yet")
        return self.model.predict_proba(X)

class MLPipeline:
    def __init__(self):
        self.preprocessor = DataPreprocessor()
        self.logger = Logger()
        self.model = None

    def build_neural_network_model(self, input_dim):
        """Build a neural network model using TradingNeuralNetwork"""
        # Use TradingNeuralNetwork for consistency
        self.model = TradingNeuralNetwork(
            input_dim=input_dim,
            hidden_layers=[64, 32, 16],
            output_dim=2,  # Binary classification: buy/sell
            learning_rate=0.001
        )
        return self.model

    def train_model(self, symbol, test_size=0.2):
        """Train the ML model on historical data"""
        try:
            self.logger.log_message('INFO', 'ML_PIPELINE', f'Starting model training for {symbol}')

            # Load processed data
            data = self.preprocessor.price_data.load_market_data(symbol)
            if data.empty:
                self.logger.log_message('ERROR', 'ML_PIPELINE', f'No data available for {symbol}')
                return None

            # Add technical indicators
            processed_data = self.preprocessor.add_technical_indicators(symbol)

            # Prepare features
            X, y, feature_cols = self.preprocessor.prepare_ml_features(processed_data)

            if len(X) == 0:
                self.logger.log_message('ERROR', 'ML_PIPELINE', 'Insufficient data for training')
                return None

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42, shuffle=False
            )

            # Normalize features
            X_train_scaled, X_test_scaled = self.preprocessor.normalize_features(X_train, X_test)

            # Build and train model
            input_dim = X_train_scaled.shape[1] * X_train_scaled.shape[2]  # Flatten for NN
            self.build_neural_network_model(input_dim)

            # Reshape for sklearn (flatten time series)
            X_train_flat = X_train_scaled.reshape(X_train_scaled.shape[0], -1)
            X_test_flat = X_test_scaled.reshape(X_test_scaled.shape[0], -1)

            # Train using TradingNeuralNetwork
            train_results = self.model.train(X_train_flat, y_train)

            # Evaluate model
            y_pred = self.model.predict(X_test_flat)
            accuracy = accuracy_score(y_test, y_pred)

            self.logger.log_message('INFO', 'ML_PIPELINE', f'Model trained with accuracy: {accuracy:.4f}')

            # Log performance
            metrics = {
                'total_trades': len(y_test),
                'accuracy': accuracy,
                'train_loss': train_results.get('train_loss', 0),
                'val_loss': train_results.get('val_loss', 0),
                'train_acc': train_results.get('train_acc', 0),
                'val_acc': train_results.get('val_acc', 0)
            }

            self.logger.log_performance(metrics)

            return {
                'model': self.model,
                'accuracy': accuracy,
                'feature_cols': feature_cols,
                'metrics': metrics
            }

        except Exception as e:
            self.logger.log_message('ERROR', 'ML_PIPELINE', f'Training failed: {str(e)}')
            return None

    def predict_signal(self, symbol):
        """Generate trading signal using trained model"""
        try:
            if self.model is None:
                self.logger.log_message('ERROR', 'ML_PIPELINE', 'No trained model available')
                return None

            # Get recent data for prediction
            data = self.preprocessor.price_data.load_market_data(symbol)
            if data.empty:
                return None

            processed_data = self.preprocessor.add_technical_indicators(symbol)
            X, _, _ = self.preprocessor.prepare_ml_features(processed_data, lookback=60, forecast_horizon=1)

            if len(X) == 0:
                return None

            # Get latest sequence
            latest_sequence = X[-1:]

            # Normalize
            X_scaled = self.preprocessor.normalize_features(latest_sequence)
            X_flat = X_scaled.reshape(X_scaled.shape[0], -1)

            # Predict
            prediction = self.model.predict(X_flat)[0]
            probabilities = self.model.predict_proba(X_flat)[0]

            signal = {
                'symbol': symbol,
                'signal': 'BUY' if prediction == 1 else 'SELL',
                'confidence': max(probabilities),
                'timestamp': pd.Timestamp.now()
            }

            self.logger.log_message('INFO', 'ML_PIPELINE', f'Generated signal: {signal}')

            return signal

        except Exception as e:
            self.logger.log_message('ERROR', 'ML_PIPELINE', f'Prediction failed: {str(e)}')
            return None

    def reinforce_learning(self, trade_result):
        """Reinforce learning based on trade results"""
        try:
            # Analyze trade result and adjust model if needed
            if trade_result.get('profit_loss', 0) < 0:  # Losing trade
                self.logger.log_message('INFO', 'ML_PIPELINE', 'Negative result detected, model reinforcement needed')

                # In a full implementation, this would:
                # 1. Analyze what went wrong
                # 2. Adjust model parameters
                # 3. Retrain on new data
                # 4. Update feature importance

                # For now, just log the reinforcement need
                reinforcement_data = {
                    'trade_id': trade_result.get('id'),
                    'loss_amount': abs(trade_result.get('profit_loss', 0)),
                    'reason': 'low_accuracy',
                    'action': 'model_update_pending'
                }

                self.logger.log_message('INFO', 'ML_PIPELINE', f'Reinforcement data: {reinforcement_data}')

            else:
                self.logger.log_message('INFO', 'ML_PIPELINE', 'Positive result, model performing well')

        except Exception as e:
            self.logger.log_message('ERROR', 'ML_PIPELINE', f'Reinforcement failed: {str(e)}')

if __name__ == "__main__":
    ml_pipeline = MLPipeline()

    # Train model on EURUSD data
    result = ml_pipeline.train_model('EURUSD')
    if result:
        print(f"Model trained with accuracy: {result['accuracy']:.4f}")

        # Generate a prediction
        signal = ml_pipeline.predict_signal('EURUSD')
        if signal:
            print(f"Trading signal: {signal}")
    else:
        print("Model training failed")