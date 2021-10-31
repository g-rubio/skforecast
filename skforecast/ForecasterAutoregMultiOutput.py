################################################################################
#                               skforecast                                     #
#                                                                              #
# This work by Joaquín Amat Rodrigo is licensed under a Creative Commons       #
# Attribution 4.0 International License.                                       #
################################################################################
# coding=utf-8

import typing
from typing import Union, Dict, List, Tuple, Any
import warnings
import logging
import numpy as np
import pandas as pd
import sklearn
import tqdm

from sklearn.base import clone
from sklearn.metrics import mean_squared_error
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_absolute_percentage_error

logging.basicConfig(
    format = '%(name)-10s %(levelname)-5s %(message)s', 
    level  = logging.INFO,
)


################################################################################
#                         ForecasterAutoregMultiOutput                         #
################################################################################

class ForecasterAutoregMultiOutput():
    '''
    This class turns any regressor compatible with the scikit-learn API into a
    autoregressive multi-output forecaster. A separate model is created for each
    forecast time step. See Notes for more details.
    
    Parameters
    ----------
    regressor : regressor compatible with the scikit-learn API
        An instance of a regressor compatible with the scikit-learn API.
        
    lags : int, list, 1d numpy ndarray, range
        Lags used as predictors. Index starts at 1, so lag 1 is equal to t-1.
            `int`: include lags from 1 to `lags` (included).
            `list`, `numpy ndarray` or range: include only lags present in `lags`.
            
    steps : int
        Number of future steps the forecaster will predict when using method
        `predict()`. Since a diferent model is created for each step, this value
        should be defined before training.
    
    Attributes
    ----------
    regressor : regressor compatible with the scikit-learn API
        An instance of regressor compatible with the scikit-learn API.
        One instance of this regressor is trainned for each step. All
        them are stored in `slef.regressors_`.
        
    regressors_ : dict
        Dictionary with regressors trained for each step.
        
    steps : int
        Number of future steps the forecaster will predict when using method
        `predict()`. Since a diferent model is created for each step, this value
        should be defined before training.
        
    lags : numpy ndarray
        Lags used as predictors.
        
    max_lag : int
        Maximum value of lag included in `lags`.

    last_window : pandas Series
        Last window the forecaster has seen during trained. It stores the
        values needed to calculate the lags used to predict the next `step`
        after the training data.
        
    window_size: int
        Size of the window needed to create the predictors. It is equal to
        `max_lag`.
        
    fitted: Bool
        Tag to identify if the regressor has been fitted (trained).
        
    index_type : type
        Index type of the inputused in training.
        
    index_freq : str
        Index frequency of the input used in training.
        
    training_range: pandas Index
        First and last index of samples used during training.
        
    included_exog : bool
        If the forecaster has been trained using exogenous variable/s.
        
    exog_type : type
        Type of exogenous variable/s used in training.
        
    exog_col_names : tuple
        Column names of exog if exog used in training is a pandas DataFrame.

    X_train_col_names : tuple
        Column names of matrix used internally for training.
        
    Notes
    -----
    A separate model is created for each forecast time step. It is important to
    note that all models share the same configuration of parameters and
    hiperparameters.
     
    '''
    
    def __init__(self, regressor, steps: int,
                 lags: Union[int, np.ndarray, list]) -> None:
        
        self.regressor     = regressor
        self.steps         = steps
        self.regressors_   = {step: clone(self.regressor) for step in range(steps)}
        self.index_type           = None
        self.index_freq           = None
        self.training_range       = None
        self.last_window          = None
        self.included_exog        = False
        self.exog_type            = None
        self.exog_col_names       = None
        self.X_train_col_names    = None
        self.fitted               = False

        if isinstance(lags, int) and lags < 1:
            raise Exception('min value of lags allowed is 1')
            
        if isinstance(lags, (list, range, np.ndarray)) and min(lags) < 1:
            raise Exception('min value of lags allowed is 1')
            
        if isinstance(lags, int):
            self.lags = np.arange(lags) + 1
        elif isinstance(lags, (list, range)):
            self.lags = np.array(lags)
        elif isinstance(lags, np.ndarray):
            self.lags = lags
        else:
            raise Exception(
                '`lags` argument must be `int`, `1D np.ndarray`, `range` or `list`. '
                f"Got {type(lags)}"
            )
            
        self.max_lag  = max(self.lags)
        self.window_size = self.max_lag
                
        
    def __repr__(self) -> str:
        '''
        Information displayed when a ForecasterAutoreg object is printed.
        '''

        info = (
            f"{'=' * len(str(type(self)))} \n"
            f"{type(self)} \n"
            f"{'=' * len(str(type(self)))} \n"
            f"Regressor: {self.regressor} \n"
            f"Lags: {self.lags} \n"
            f"Window size: {self.window_size} \n"
            f"Included exogenous: {self.included_exog} \n"
            f"Type of exogenous variable: {self.exog_type} \n"
            f"Exogenous variables names: {self.exog_col_names} \n"
            f"Training range: {self.training_range.to_list() if self.fitted else None} \n"
            f"Training index type: {str(self.index_type) if self.fitted else None} \n"
            f"Training index frequancy: {self.index_freq if self.fitted else None} \n"
            f"Regressor parameters: {self.regressor.get_params()} \n"
        )

        return info
    
    
    def _create_lags(self, y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        '''       
        Transforms a 1d array into a 2d array (X) and a 1d array (y).
        Each value of y is associated with a row in X that represents the lags
        that precede it.
        
        Notice that, the returned matrix X_data, contains the lag 1 in the first
        column, the lag 2 in the second column and so on.
        
        Parameters
        ----------        
        y : 1d numpy ndarray
            Training time series.

        Returns 
        -------
        X_data : 2d numpy ndarray, shape (samples - max(self.lags), len(self.lags))
            2d numpy array with the lag values (predictors).
        
        y_data : 2d numpy ndarray, shape (samples - max(self.lags),)
            Values of the time series related to each row of `X_data` for each step.
            
        '''
          
        n_splits = len(y) - self.max_lag - (self.steps -1)
        X_data  = np.full(shape=(n_splits, self.max_lag), fill_value=np.nan, dtype=float)
        y_data  = np.full(shape=(n_splits, self.steps), fill_value=np.nan, dtype= float)

        for i in range(n_splits):
            X_index = np.arange(i, self.max_lag + i)
            y_index = np.arange(self.max_lag + i, self.max_lag + i + self.steps)

            X_data[i, :] = y[X_index]
            y_data[i, :] = y[y_index]
            
        X_data = X_data[:, -self.lags]
            
        return X_data, y_data


    def create_train_X_y(
        self,
        y: pd.Series,
        exog: Union[pd.Series, pd.DataFrame]=None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        '''
        Create training matrices X, y. The created matrices contain the target
        variable and predictors needed to train all the forecaster (one per step).         
        
        Parameters
        ----------        
        y : pandas Series
            Training time series.
            
        exog : pandas Series, pandas DataFrame, default `None`
            Exogenous variable/s included as predictor/s. Must have the same
            number of observations as `y` and their indexes must be aligned.


        Returns 
        -------
        X_train : pandas DataFrame, shape (len(y) - self.max_lag, len(self.lags) + exog.shape[1]*steps)
            Pandas DataFrame with the training values (predictors) for each step.
            
        y_train : pd.DataFrame, shape (len(y) - self.max_lag, )
            Values (target) of the time series related to each row of `X_train` 
            for each step.
        
        '''

        self._check_y(y=y)
        y_values, y_index = self._preproces_y(y=y)

        if exog is not None:
            if len(exog) != len(y):
                raise Exception(
                    "`exog` must have same number of samples as `y`."
                )
            self._check_exog(exog=exog)
            exog_values, exog_index = self._preproces_exog(exog=exog)
            if not (exog_index[:len(y_index)] == y_index).all():
                raise Exception(
                ('Different index for `y` and `exog`. They must be equal '
                'to ensure the correct aligment of values.')      
                )
      
        X_lags, y_train = self._create_lags(y=y_values)
        col_names_y_train = [f"y_step_{i}" for i in range(self.steps)]
        col_names_X_train = [f"lag_{i}" for i in self.lags]

        if exog is None:
            X_train = X_lags
        else:
            col_names_exog = exog.columns if isinstance(exog, pd.DataFrame) else [exog.name]
            # Trasform exog to match multi output format
            X_exog = self._exog_to_multi_output(exog=exog_values)
            col_names_exog = [f"{col_name}_step_{i+1}" for col_name in col_names_exog for i in range(self.steps)]
            col_names_X_train.extend(col_names_exog)
            # The first `self.max_lag` positions have to be removed from X_exog
            # since they are not in X_lags.
            X_exog = X_exog[-X_lags.shape[0]:, ]
            X_train = np.column_stack((X_lags, X_exog))

        X_train = pd.DataFrame(
                    data    = X_train,
                    columns = col_names_X_train,
                    index   = y_index[self.max_lag + (self.steps -1): ]
                  )
        self.X_train_col_names = col_names_X_train
        y_train = pd.DataFrame(
                    data  = y_train,
                    index = y_index[self.max_lag + (self.steps -1): ],
                    columns = col_names_y_train,
                 )
                        
        return X_train, y_train

    
    def filter_train_X_y_for_step(
        self,
        step: int,
        X_train: pd.DataFrame,
        y_train: pd.Series
    ) -> Tuple[pd.DataFrame, pd.Series]:

        '''
        Select columns needed to train a forcaster for a specific step. The imput
        matrices should be created with created with `create_train_X_y()`.         

        Parameters
        ----------
        step : int
            step for which columns must be selected selected. Starts at 0.

        X_train : pandas DataFrame
            Pandas DataFrame with the training values (predictors).
            
        y_train : pandas Series
            Values (target) of the time series related to each row of `X_train`.


        Returns 
        -------
        X_train_step : pandas DataFrame
            Pandas DataFrame with the training values (predictors) for step.
            
        y_train_step : pandas Series, shape (len(y) - self.max_lag)
            Values (target) of the time series related to each row of `X_train`.

        '''

        if step > self.steps - 1:
            raise Exception(
                f"Invalid value `step`. For this forecaster, the maximum step is {self.steps-1}."
            )

        y_train_step = y_train.iloc[:, step]

        if not self.included_exog:
            X_train_step = X_train
        else:
            idx_columns_lags = np.arange(len(self.lags))
            idx_columns_exog = np.arange(X_train.shape[1])[len(self.lags) + step::self.steps]
            idx_columns = np.hstack((idx_columns_lags, idx_columns_exog))
            X_train_step = X_train.iloc[:, idx_columns]

        return  X_train_step, y_train_step
    
    
    def fit(
        self,
        y: pd.Series,
        exog: Union[pd.Series, pd.DataFrame]=None
    ) -> None:
        '''
        Training Forecaster.
        
        Parameters
        ----------        
        y : pandas Series
            Training time series.
            
        exog : pandas Series, pandas DataFrame, default `None`
            Exogenous variable/s included as predictor/s. Must have the same
            number of observations as `y` and their indexes must be aligned so
            that y[i] is regressed on exog[i].


        Returns 
        -------
        None
        
        '''

        # Reset values in case the forecaster has already been fitted.
        self.index_type           = None
        self.index_freq           = None
        self.last_window          = None
        self.included_exog        = False
        self.exog_type            = None
        self.exog_col_names       = None
        self.X_train_col_names    = None
        self.fitted               = False
        self.training_range       = None

        if exog is not None:
            self.included_exog = True
            self.exog_type = type(exog)
            self.exog_col_names = \
                 exog.columns.to_list() if isinstance(exog, pd.DataFrame) else exog.name

        X_train, y_train = self.create_train_X_y(y=y, exog=exog)
        
        # Train one regressor for each step 
        for step in range(self.steps):

            X_train_step, y_train_step = self.filter_train_X_y_for_step(
                                            step    = step,
                                            X_train = X_train,
                                            y_train = y_train
                                         ) 
            self.regressors_[step].fit(X_train_step, y_train_step)
        
        self.fitted = True
        self.training_range = self._preproces_y(y=y)[1][[0, -1]]
        self.index_type = type(X_train.index)
        if isinstance(X_train.index, pd.DatetimeIndex):
            self.index_freq = X_train.index.freqstr
        else: 
            self.index_freq = X_train.index.step

        # The last time window of training data is stored so that lags needed as
        # predictors in the first iteration of `predict()` can be calculated.
        # self.last_window = y_train.iloc[-self.max_lag:, -1]
        # if self.steps >= self.max_lag:
        #     self.last_window = y_train.iloc[-1, -self.max_lag:]
        # else:
        #     self.last_window = pd.concat((
        #                             y_train.iloc[-(self.max_lag-self.steps + 1):-1, 0],
        #                             y_train.iloc[-1, :]
        #                        ))

        self.last_window = y_train.iloc[-self.max_lag:, -1]
    
    def predict(
        self,
        last_window: pd.Series=None,
        exog: Union[pd.Series, pd.DataFrame]=None,
        steps = None
    ) -> np.ndarray:
        '''
        Predict n steps ahead. The number of future steps predicted is defined when
        ininitializing the forecaster. Argument `steps` not used, present here for
        API consistency by convention.

        Parameters
        ----------
        last_window : pandas Series, default `None`
            Values of the series used to create the predictors (lags) need in the 
            first iteration of predictiont (t + 1).
    
            If `last_window = None`, the values stored in` self.last_window` are
            used to calculate the initial predictors, and the predictions start
            right after training data.
            
        exog : pandas Series, pandas DataFrame, default `None`
            Exogenous variable/s included as predictor/s.

        steps : Ignored
            Not used, present here for API consistency by convention.

        Returns 
        -------
        predictions : pandas Series
            Predicted values.

        '''

        steps = self.steps
        self._check_predict_input(
            steps       = steps,
            last_window = last_window, 
            exog        = exog
        )

        if exog is not None:
            if isinstance(exog, pd.DataFrame):
                exog_values, exog_index = self._preproces_exog(
                                            exog = exog[self.exog_col_names].iloc[:steps, ]
                                        )
            else: 
                exog_values, exog_index = self._preproces_exog(
                                            exog = exog.iloc[:steps, ]
                                        )
            exog_values = self._exog_to_multi_output(exog=exog_values)
        else:
            exog_values = None
            exog_index = None

        if last_window is not None:
            last_window_values, last_window_index = self._preproces_last_window(
                                                        last_window = last_window
                                                    )  
        else:
            last_window_values, last_window_index = self._preproces_last_window(
                                                        last_window = self.last_window
                                                    )


        predictions = np.full(shape=steps, fill_value=np.nan)
        X_lags = last_window_values[-self.lags].reshape(1, -1)

        for step in range(steps):
            regressor = self.regressors_[step]
            if exog is None:
                X = X_lags
            else:
                # Only columns from exog related with the current step are selected.
                X = np.hstack([X_lags, exog_values[0][step::steps].reshape(1, -1)])
            with warnings.catch_warnings():
                # Supress scikitlearn warning: "X does not have valid feature names,
                # but NoOpTransformer was fitted with feature names".
                warnings.simplefilter("ignore")
                predictions[step] = regressor.predict(X)

        predictions = pd.Series(
                        data  = predictions.reshape(-1),
                        index = self._expand_index(
                                    index = last_window_index,
                                    steps = steps
                                ),
                        name = 'pred'
                      )

        return predictions
        
    
    
    @staticmethod
    def _check_y(y: Any) -> None:
        '''
        Raise Exception if `y` is not pandas Series or if it has missing values.
        
        Parameters
        ----------        
        y : Any
            Time series values
            
        Returns
        ----------
        None
        
        '''
        
        if not isinstance(y, pd.Series):
            raise Exception('`y` must be a pandas Series.')
            
        if y.isnull().any():
            raise Exception('`y` has missing values.')
        
        return

        
    @staticmethod
    def _check_exog(exog: Any) -> None:
        '''
        Raise Exception if `exog` is not pandas Series or DataFrame, or
        if it has missing values.
        
        Parameters
        ----------        
        exog :  Any
            Exogenous variable/s included as predictor/s.

        Returns
        ----------
        None
        '''
            
        if not isinstance(exog, (pd.Series, pd.DataFrame)):
            raise Exception('`exog` must be `pd.Series` or `pd.DataFrame`.')

        if exog.isnull().any().any():
            raise Exception('`exog` has missing values.')
                    
        return
    
    def _check_predict_input(
        self,
        steps: int,
        last_window: pd.Series=None,
        exog: Union[pd.Series, pd.DataFrame]=None
    ) -> None:
        '''
        Check all inputs of predict method
        '''

        if not self.fitted:
            raise Exception(
                'This Forecaster instance is not fitted yet. Call `fit` with'
                'appropriate arguments before using predict.'
            )
        
        if steps < 1:
            raise Exception(
                f"`steps` must be integer greater than 0. Got {steps}."
            )
        
        if exog is None and self.included_exog:
            raise Exception(
                'Forecaster trained with exogenous variable/s. '
                'Same variable/s must be provided in `predict()`.'
            )
            
        if exog is not None and not self.included_exog:
            raise Exception(
                'Forecaster trained without exogenous variable/s. '
                '`exog` must be `None` in `predict()`.'
            )
        
        if exog is not None:
            if len(exog) < steps:
                raise Exception(
                    '`exog` must have at least as many values as `steps` predicted.'
                )
            if not isinstance(exog, self.exog_type):
                raise Exception(
                    f"Expected type for `exog`: {self.exog_type}. Got {type(exog)}"      
                )
            if isinstance(exog, pd.DataFrame):
                col_missing = set(self.exog_col_names).difference(set(exog.columns))
                if col_missing:
                    raise Exception(
                        f"Missing columns in `exog`. Expected {self.exog_col_names}. "
                        f"Got {exog.columns.to_list()}"      
                    )
            self._check_exog(exog = exog)
            exog_values, exog_index = self._preproces_exog(
                                        exog = exog.iloc[:0, ]
                                      )
            
            if not isinstance(exog_index, self.index_type):
                raise Exception(
                    f"Expected index of type {self.index_type} for `exog`. "
                    f"Got {type(exog_index)}"      
                )
            if not exog_index.freqstr == self.index_freq:
                raise Exception(
                    f"Expected frequency of type {self.index_type} for `exog`. "
                    f"Got {exog_index.freqstr}"      
                )
            
        if last_window is not None:
            if len(last_window) < self.max_lag:
                raise Exception(
                    f"`last_window` must have as many values as as needed to "
                    f"calculate the maximum lag ({self.max_lag})."
                )
            if not isinstance(last_window, pd.Series):
                raise Exception('`last_window` must be a pandas Series.')
            if last_window.isnull().any():
                raise Exception('`last_window` has missing values.')
            last_window_values, last_window_index = \
                self._preproces_last_window(
                    last_window = last_window.iloc[:0]
                ) 
            if not isinstance(last_window_index, self.index_type):
                raise Exception(
                    f"Expected index of type {self.index_type} for `last_window`. "
                    f"Got {type(last_window_index)}"      
                )
            if not last_window_index.freqstr == self.index_freq:
                raise Exception(
                    f"Expected frequency of type {self.index_type} for `last_window`. "
                    f"Got {last_window_index.freqstr}"      
                )

        return    


    @staticmethod
    def _preproces_y(y: pd.Series) -> Union[np.ndarray, pd.Index]:
        
        '''
        Returns values ​​and index of series separately. Index is overwritten
        according to the next rules:
            If index is not of type DatetimeIndex, a RangeIndex is created.
            If index is of type DatetimeIndex and but has no frequency, a
            RangeIndex is created.
            If index is of type DatetimeIndex and has frequency, nothing is
            changed.
        
        Parameters
        ----------        
        y : pandas Series
            Time series values

        Returns 
        -------
        y_values : numpy ndarray
            Numpy array with values of `y`.

        y_index : pandas Index
            Index of of `y` modified according to the rules.
        '''
        
        if isinstance(y.index, pd.DatetimeIndex) and y.index.freq is not None:
            y_index = y.index
        else:
            warnings.warn(
                '`y` has DatetimeIndex index but no frequency. Index is overwritten with a RangeIndex.'
            )
            y_index = pd.RangeIndex(
                        start = 0,
                        stop  = len(y),
                        step  = 1
                       )

        y_values = y.to_numpy()

        return y_values, y_index
        

    @staticmethod
    def _preproces_last_window(last_window: pd.Series) -> Union[np.ndarray, pd.Index]:
        
        '''
        Returns values ​​and index of series separately. Index is overwritten
        according to the next rules:
            If index is not of type DatetimeIndex, a RangeIndex is created.
            If index is of type DatetimeIndex and but has no frequency, a
            RangeIndex is created.
            If index is of type DatetimeIndex and has frequency, nothing is
            changed.
        
        Parameters
        ----------        
        last_window : pandas Series
            Time series values

        Returns 
        -------
        last_window_values : numpy ndarray
            Numpy array with values of `last_window`.

        last_window_index : pandas Index
            Index of of `last_window` modified according to the rules.
        '''
        
        if isinstance(last_window.index, pd.DatetimeIndex) and last_window.index.freq is not None:
            last_window_index = last_window.index
        else:
            warnings.warn(
                '`last_window` has DatetimeIndex index but no frequency. '
                'Index is overwritten with a RangeIndex.'
            )
            last_window_index = pd.RangeIndex(
                        start = 0,
                        stop  = len(last_window),
                        step  = 1
                       )

        last_window_values = last_window.to_numpy()

        return last_window_values, last_window_index
        
        
    @staticmethod
    def _preproces_exog(
        exog: Union[pd.Series, pd.DataFrame]
    ) -> Union[np.ndarray, pd.Index]:
        
        '''
        Returns values ​​and index separately. Index is overwritten according to
        the next rules:
            If index is not of type DatetimeIndex, a RangeIndex is created.
            If index is of type DatetimeIndex and but has no frequency, a
            RangeIndex is created.
            If index is of type DatetimeIndex and has frequency, nothing is
            changed.

        Parameters
        ----------        
        exog : pd.Series, pd.DataFrame
            Exogenous variables

        Returns 
        -------
        exog_values : np.ndarray
            Numpy array with values of `exog`.
        exog_index : pd.Index
            Exog index.
        '''
        
        if isinstance(exog.index, pd.DatetimeIndex) and exog.index.freq is not None:
            exog_index = exog.index
        else:
            warnings.warn(
                ('`exog` has DatetimeIndex index but no frequency. The index is '
                 'overwritten with a RangeIndex.')
            )
            exog_index = pd.RangeIndex(
                            start = 0,
                            stop  = len(exog),
                            step  = 1
                          )

        exog_values = exog.to_numpy()

        return exog_values, exog_index
    

    def _exog_to_multi_output(self, exog: np.ndarray)-> np.ndarray:
        
        '''
        Transforms `exog` to `np.ndarray` with the shape needed for multioutput
        regresors.
        
        Parameters
        ----------        
        exog : numpy ndarray, shape(samples,)
            Time series values

        Returns 
        -------
        exog_transformed: numpy ndarray, shape(samples - self.max_lag, self.steps)
        '''

        exog_transformed = []

        if exog.ndim < 2:
            exog = exog.reshape(-1, 1)

        for column in range(exog.shape[1]):

            exog_column_transformed = []

            for i in range(exog.shape[0] - (self.steps -1)):
                exog_column_transformed.append(exog[i:i + self.steps, column])

            if len(exog_column_transformed) > 1:
                exog_column_transformed = np.vstack(exog_column_transformed)

            exog_transformed.append(exog_column_transformed)

        if len(exog_transformed) > 1:
            exog_transformed = np.hstack(exog_transformed)
        else:
            exog_transformed = exog_column_transformed

        return exog_transformed


    @staticmethod
    def _expand_index(index: Union[pd.Index, None], steps: int) -> pd.Index:
        
        '''
        Create a new index of lenght `steps` starting and the end of index.
        
        Parameters
        ----------        
        index : pd.Index, None
            Index of last window
        steps: int
            Number of steps to expand.

        Returns 
        -------
        new_index : pd.Index
        '''
        
        if isinstance(index, pd.Index):
            
            if isinstance(index, pd.DatetimeIndex):
                new_index = pd.date_range(
                                index[-1] + index.freq,
                                periods = steps,
                                freq    = index.freq
                            )
            elif isinstance(index, pd.RangeIndex):
                new_index = pd.RangeIndex(
                                start = index[-1] + 1,
                                stop  = index[-1] + 1 + steps
                             )
        else: 
            new_index = pd.RangeIndex(
                            start = 0,
                            stop  = steps
                         )
        return new_index
    
    
    def set_params(self, **params: dict) -> None:
        '''
        Set new values to the parameters of the scikit learn model stored in the
        forecaster. It is important to note that all models share the same 
        configuration of parameters and hiperparameters.
        
        Parameters
        ----------
        params : dict
            Parameters values.

        Returns 
        -------
        self
        
        '''
        
        self.regressor.set_params(**params)
        self.regressors_ = {step: clone(self.regressor) for step in range(self.steps)}
        
        
        
    def set_lags(self, lags: int) -> None:
        '''      
        Set new value to the attribute `lags`.
        Attributes `max_lag` and `window_size` are also updated.
        
        Parameters
        ----------
        lags : int, list, 1D np.array, range
        Lags used as predictors. Index starts at 1, so lag 1 is equal to t-1.
            `int`: include lags from 1 to `lags`.
            `list` or `np.array`: include only lags present in `lags`.

        Returns 
        -------
        self
        
        '''
        
        if isinstance(lags, int) and lags < 1:
            raise Exception('min value of lags allowed is 1')
            
        if isinstance(lags, (list, range, np.ndarray)) and min(lags) < 1:
            raise Exception('min value of lags allowed is 1')
            
        if isinstance(lags, int):
            self.lags = np.arange(lags) + 1
        elif isinstance(lags, (list, range)):
            self.lags = np.array(lags)
        elif isinstance(lags, np.ndarray):
            self.lags = lags
        else:
            raise Exception(
                f"`lags` argument must be `int`, `1D np.ndarray`, `range` or `list`. "
                f"Got {type(lags)}"
            )
            
        self.max_lag  = max(self.lags)
        self.window_size = max(self.lags)
        

    def get_coef(self, step) -> np.ndarray:
        '''      
        Return estimated coefficients for the linear regression model stored in
        the forecaster for a specific step. Since a separate model is created for
        each forecast time step, it is necessary to select the model from which
        retireve information.
        
        Only valid when the forecaster has been trained using as `regressor:
        `LinearRegression()`, `Lasso()` or `Ridge()`.
        
        Parameters
        ----------
        step : int
            Model from which retireve information (a separate model is created for
            each forecast time step).

        Returns 
        -------
        coef : pandas DataFrame
            Value of the coefficients associated with each predictor.
        
        '''
        
        if step > self.steps:
            raise Exception(
                f"Forecaster traied for {self.steps} steps. Got step={step}."
            )
            
        
        valid_instances = (sklearn.linear_model._base.LinearRegression,
                           sklearn.linear_model._coordinate_descent.Lasso,
                           sklearn.linear_model._ridge.Ridge
                           )
        
        if not isinstance(self.regressor, valid_instances):
            warnings.warn(
                ('Only forecasters with `regressor` `LinearRegression()`, ' +
                 ' `Lasso()` or `Ridge()` have coef.')
            )
            return
        else:
            coef = pd.DataFrame({
                        'feature': self.X_train_col_names,
                        'coef' : self.regressors_[step-1].coef_
                   })
            
        return coef

    
    def get_feature_importances(self, step) -> np.ndarray:
        '''      
        Return impurity-based feature importances of the model stored in
        the forecaster for a specific step. Since a separate model is created for
        each forecast time step, it is necessary to select the model from which
        retireve information.
        
        Only valid when the forecaster has been trained using
        `GradientBoostingRegressor` , `RandomForestRegressor` or 
        `HistGradientBoostingRegressor` as regressor.

        Parameters
        ----------
        step : int
            Model from which retireve information (a separate model is created for
            each forecast time step).

        Returns 
        -------
        feature_importances : pandas DataFrame
            Impurity-based feature importances associated with each predictor.
        '''
        
        if step > self.steps:
            raise Exception(
                f"Forecaster traied for {self.steps} steps. Got step={step}."
            )
        
        valid_instances = (sklearn.ensemble._forest.RandomForestRegressor,
                           sklearn.ensemble._gb.GradientBoostingRegressor,
                           sklearn.ensemble.HistGradientBoostingRegressor)

        if not isinstance(self.regressor, valid_instances):
            warnings.warn(
                ('Only valid when the forecaster has been trained using ',
                 '`GradientBoostingRegressor` , `RandomForestRegressor` or ',
                 '`HistGradientBoostingRegressor` as regressor.')
            )
            return
        else:
            feature_importance = pd.DataFrame({
                                    'feature': self.X_train_col_names,
                                    'importance' : self.regressors_[step-1].feature_importances_
                                })

        return feature_importance