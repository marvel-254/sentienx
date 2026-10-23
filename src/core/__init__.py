"""
SENTIENX Advanced Core Framework
Base classes for forecasters and agents with unified data processing
"""

import os
import pickle
import dill
import json
import datetime
from abc import ABC, abstractmethod
import numpy as np

class DataProcessor(ABC):
    """
    The Data Processing Framework for SENTIENX
    
    Provides unified way to specify data processing methods for different models.
    This helps models built to be more portable and reusable anywhere.
    
    Attributes
    ----------
    tickers : list
        A list of all tickers to be used for model
    features : list
        A list of features needed for each ticker
    tickerData : dict
        A dictionary containing pandas DataFrame for each ticker
    interval : str
        Parameter specifying data interval to be fetched and trained on
    lookBack : int
        Number of days to look back for predictions
    forecast : int
        Number of days to forecast into the future
    """
    
    def __init__(self, tickers, features, lookBack, forecast, interval="1d"):
        self.tickers = tickers
        self.features = features
        self.lookBack = lookBack
        self.forecast = forecast
        self.interval = interval.upper()
        self.tickerData = {}
        
    @abstractmethod
    def inputProcessor(self, data, context):
        """
        Process raw ticker data into model-compatible format
        
        Parameters
        ----------
        data : dict
            The dict containing raw ticker data
        context : dict
            Context dictionary containing usage information
            
        Returns
        -------
        X : np.array
            The input data for model
        Y : np.array, optional
            The target for model (for training)
        """
        pass
    
    @abstractmethod
    def outputProcessor(self, modelOut, context):
        """
        Process model output into required values
        
        Parameters
        ----------
        modelOut : np.array
            The raw output from model
        context : dict
            Context dictionary containing usage information
            
        Returns
        -------
        processed : np.array
            The processed output
        """
        pass
    
    def getTrainingData(self, validationSplit=0.7, shuffle=True, batchSize=64):
        """
        Prepare training data with validation split
        
        Parameters
        ----------
        validationSplit : float
            Ratio for training/validation split
        shuffle : bool
            Whether to shuffle data before training
        batchSize : int
            Batch size for training
            
        Returns
        -------
        trainData : tuple
            Training data (X, Y)
        validData : tuple
            Validation data (X, Y)
        """
        pass
    
    def saveProcessor(self, path):
        """Save data processor configuration"""
        config = {
            'tickers': self.tickers,
            'features': self.features,
            'lookBack': self.lookBack,
            'forecast': self.forecast,
            'interval': self.interval,
            'class_name': self.__class__.__name__
        }
        
        with open(path, 'wb') as f:
            dill.dump(self, f)
        
        with open(path.replace('.dill', '.json'), 'w') as f:
            json.dump(config, f, indent=2)

class ForecasterBase(ABC):
    """
    Base class for all forecasting models
    
    Attributes
    ----------
    model : object
        The trained model
    history : dict
        Training history and metrics
    dataProcessor : DataProcessor
        The data processor for this model
    """
    
    def __init__(self):
        self.model = None
        self.history = None
        self.dataProcessor = None
        
    @abstractmethod
    def buildModel(self, learningRate=1e-3):
        """
        Build the model architecture
        
        Parameters
        ----------
        learningRate : float
            Learning rate for optimizer
        """
        pass
    
    def assignDataProcessor(self, dataProcessor):
        """Assign data processor to this model"""
        self.dataProcessor = dataProcessor
        self.lookBack = dataProcessor.lookBack
        self.forecast = dataProcessor.forecast
        
    def train(self, epochs=100, validationSplit=0.7, earlyStopping=True, 
              patience=10, batchSize=64, shuffle=True):
        """
        Train the model
        
        Parameters
        ----------
        epochs : int
            Number of training epochs
        validationSplit : float
            Validation split ratio
        earlyStopping : bool
            Whether to use early stopping
        patience : int
            Patience for early stopping
        batchSize : int
            Batch size for training
        shuffle : bool
            Whether to shuffle training data
        """
        pass
    
    def predict(self, data):
        """
        Make predictions on new data
        
        Parameters
        ----------
        data : dict or np.array
            Input data for predictions
            
        Returns
        -------
        predictions : np.array
            Model predictions
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")
        
        if isinstance(data, dict):
            context = {"isTrain": False}
            processedInput = self.dataProcessor.inputProcessor(data, context)
        else:
            processedInput = data
            
        predictions = self.model.predict(processedInput)
        return self.dataProcessor.outputProcessor(predictions, {"isTrain": False})
    
    def saveModel(self, name, savePath="models/forecasters/"):
        """
        Save model with metadata
        
        Parameters
        ----------
        name : str
            Model name
        savePath : str
            Path to save model
        """
        if not os.path.exists(savePath):
            os.makedirs(savePath)
            
        modelPath = os.path.join(savePath, name)
        if not os.path.exists(modelPath):
            os.makedirs(modelPath)
        
        # Save model
        if hasattr(self.model, 'save'):
            self.model.save(os.path.join(modelPath, "model.h5"))
        
        # Save data processor
        with open(os.path.join(modelPath, "data_processor.dill"), 'wb') as f:
            dill.dump(self.dataProcessor, f)
        
        # Save metadata
        metadata = {
            'model_name': name,
            'class_name': self.__class__.__name__,
            'tickers': self.dataProcessor.tickers,
            'features': self.dataProcessor.features,
            'lookBack': self.dataProcessor.lookBack,
            'forecast': self.dataProcessor.forecast,
            'interval': self.dataProcessor.interval,
            'saved_at': str(datetime.datetime.now()),
            'training_history': self.history
        }
        
        with open(os.path.join(modelPath, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
    
    def loadModel(self, name, savePath="models/forecasters/"):
        """
        Load saved model
        
        Parameters
        ----------
        name : str
            Model name to load
        savePath : str
            Path where model is saved
        """
        modelPath = os.path.join(savePath, name)
        
        # Load data processor
        with open(os.path.join(modelPath, "data_processor.dill"), 'rb') as f:
            self.dataProcessor = dill.load(f)
        
        # Load model
        if os.path.exists(os.path.join(modelPath, "model.h5")):
            self.model = self._loadModelFile(os.path.join(modelPath, "model.h5"))
        
        # Load metadata
        with open(os.path.join(modelPath, "metadata.json"), 'r') as f:
            metadata = json.load(f)
        
        self.history = metadata.get('training_history', None)
        return metadata
    
    @abstractmethod
    def _loadModelFile(self, path):
        """Load model file - to be implemented by subclasses"""
        pass

class AgentBase(ABC):
    """
    Base class for all trading agents
    
    Attributes
    ----------
    dataProcessor : DataProcessor
        The data processor assigned to this agent
    orderBook : list
        List of actions taken by the agent
    initialMoney : float
        Initial capital for trading
    money : float
        Current money remaining
    profit : float
        Current profit/loss
    history : dict
        Training and performance history
    """
    
    def __init__(self, initialMoney=10000):
        self.dataProcessor = None
        self.orderBook = []
        self.initialMoney = initialMoney
        self.money = initialMoney
        self.profit = 0
        self.history = {}
        
        # Initialize actions
        self.ACTION_BUY = 0
        self.ACTION_SELL = 1
        self.ACTION_HOLD = 2
        self.allActions = [self.ACTION_BUY, self.ACTION_SELL, self.ACTION_HOLD]
        self.actionSize = len(self.allActions)
    
    def assignDataProcessor(self, dataProcessor):
        """Assign data processor to this agent"""
        self.dataProcessor = dataProcessor
        self.lookBack = dataProcessor.lookBack
        self.tickerData = dataProcessor.tickerData.copy()
    
    @abstractmethod
    def buildModel(self, learningRate=1e-3):
        """
        Build the agent model
        
        Parameters
        ----------
        learningRate : float
            Learning rate for training
        """
        pass
    
    @abstractmethod
    def getAction(self, state, context=None):
        """
        Get action from model given current state
        
        Parameters
        ----------
        state : np.array
            Current market state
        context : dict, optional
            Additional context information
            
        Returns
        -------
        action : int
            Chosen action (BUY, SELL, HOLD)
        """
        pass
    
    def handleAction(self, action, price):
        """
        Handle action execution and update portfolio
        
        Parameters
        ----------
        action : int
            Action taken by agent
        price : float
            Price at which action was executed
        """
        if action == self.ACTION_BUY and self.money >= price:
            self.orderBook.append(price)
            self.money -= price
        elif action == self.ACTION_SELL and len(self.orderBook) > 0:
            lastPrice = self.orderBook.pop(0)
            self.profit += price - lastPrice
            self.money += price
    
    def train(self, epochs=100, logFreq=10):
        """
        Train the agent
        
        Parameters
        ----------
        epochs : int
            Number of training epochs
        logFreq : int
            Frequency of logging progress
        """
        pass
    
    def saveModel(self, name, savePath="models/agents/"):
        """
        Save agent model and metadata
        
        Parameters
        ----------
        name : str
            Agent name
        savePath : str
            Path to save agent
        """
        if not os.path.exists(savePath):
            os.makedirs(savePath)
            
        agentPath = os.path.join(savePath, name)
        if not os.path.exists(agentPath):
            os.makedirs(agentPath)
        
        # Save model
        if hasattr(self, 'model') and self.model is not None:
            self._saveModelFile(os.path.join(agentPath, "model"))
        
        # Save data processor
        with open(os.path.join(agentPath, "data_processor.dill"), 'wb') as f:
            dill.dump(self.dataProcessor, f)
        
        # Save metadata
        metadata = {
            'agent_name': name,
            'class_name': self.__class__.__name__,
            'tickers': self.dataProcessor.tickers,
            'features': self.dataProcessor.features,
            'lookBack': self.dataProcessor.lookBack,
            'interval': self.dataProcessor.interval,
            'initial_money': self.initialMoney,
            'saved_at': str(datetime.datetime.now()),
            'training_history': self.history
        }
        
        with open(os.path.join(agentPath, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
    
    @abstractmethod
    def _saveModelFile(self, path):
        """Save model file - to be implemented by subclasses"""
        pass
    
    @abstractmethod
    def _loadModelFile(self, path):
        """Load model file - to be implemented by subclasses"""
        pass
    
    def getPortfolioValue(self, currentPrice):
        """
        Calculate current portfolio value
        
        Parameters
        ----------
        currentPrice : float
            Current market price
            
        Returns
        -------
        portfolioValue : float
            Total portfolio value
        """
        holdingsValue = len(self.orderBook) * currentPrice
        return self.money + holdingsValue
    
    def getPerformanceMetrics(self):
        """
        Get performance metrics
        
        Returns
        -------
        metrics : dict
            Performance statistics
        """
        totalReturn = (self.money + sum(self.orderBook)) - self.initialMoney
        returnPct = (totalReturn / self.initialMoney) * 100
        
        return {
            'total_return': totalReturn,
            'return_percentage': returnPct,
            'current_money': self.money,
            'holdings': len(self.orderBook),
            'profit': self.profit
        }