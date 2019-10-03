from os import path, makedirs
import pickle
import numpy as np
from sklearn import neighbors, svm, ensemble, neural_network
from sklearn.metrics import make_scorer, classification_report, confusion_matrix, f1_score, precision_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from skopt import BayesSearchCV
from skopt.space import Integer, Real, Categorical

BASE_DIR = path.dirname(__file__)
PATH_TO_PKL = 'trained_classifier.pkl'

models = [
    "random_forest",
    "knn",
    "svm",
    "mlp"
]


class FaceClassifier:
    def __init__(self, model_path=None):

        self.model = None
        if model_path is None:
            return
        elif model_path == 'default':
            model_path = path.join(BASE_DIR, PATH_TO_PKL)

        # Load models
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)

    def parameter_tuning(self, model, cv, images_per_person, X, y):

        if model == "svm":
            parameter_space = {
                'C': (0.0001, 10000.0),
                'gamma': (0.00001, 1.0),
                'degree': (1, 9),  # integer valued parameter
                'kernel': ['linear', 'poly', 'rbf', 'sigmoid', 'precomputed'],  # categorical parameter
                'tol': (0.00001, 0.1)
            }
            clf = svm.SVC()

        elif model == "knn":
            parameter_space = {
                'n_neighbors': (1, 2*images_per_person),
                'weights': ['uniform', 'distance'],
                'algorithm': ['auto', 'ball_tree', 'kd_tree', 'brute'],
                'leaf_size': (5, 150),
                'p': (1, 9)
            }
            clf = neighbors.KNeighborsClassifier()

        elif model == "mlp":
            parameter_space = {
                # 'layer1': Integer(5, 100),
                # 'layer2': Integer(0, 100),
                # 'layer3': Integer(0, 100),
                'hidden_layer_sizes': Integer(5, 100),
                # numpy.arange(0.005, 0.1, 0.005)
                'activation': Categorical(['relu', 'tanh', 'logistic']),
                'solver': Categorical(['adam', 'sgd', 'lbfgs']),
                'alpha': Real(0.0001, 0.1),
                'learning_rate': Categorical(['constant', 'adaptive']),
                'learning_rate_init': Real(0.001, 0.2),
                'max_iter': Integer(9999, 10001)
            }
            clf = neural_network.MLPClassifier()

        else:
            parameter_space = {
                'n_estimators': (5, 180),
                'criterion': ['gini', 'entropy'],
                'min_samples_split': (2, 20),
                'min_samples_leaf': (1, 20),
                'max_depth': (2, 150)
                # 'max_features': [int,]
            }
            clf = ensemble.RandomForestClassifier()
        score = make_scorer(f1_score, average='weighted')
        clf = BayesSearchCV(estimator=clf, search_spaces=parameter_space, n_iter=60, cv=cv,
                            scoring=score, verbose=True, n_jobs=-1)
        clf.fit(X, y)
        self.model = clf.best_estimator_
        return clf.best_score_

    def train(self, X, y, model='knn', num_sets=10, k_fold=False, hyperparameter_tuning=True, save_model_path=None,
              images_per_person=10):

        if hyperparameter_tuning is True:
            cv = StratifiedKFold(n_splits=num_sets)
            score = self.parameter_tuning(model, cv, images_per_person, X, y)
        elif k_fold is True:
            pass
        else:
            if num_sets > 1:
                X, X_test, y, y_test = train_test_split(X, y, stratify=y, test_size=1/num_sets)
            if model == 'knn':
                self.model = neighbors.KNeighborsClassifier(n_neighbors=10, weights='distance', p=9, leaf_size=90)
            elif model == 'random_forest':
                self.model = ensemble.RandomForestClassifier(n_estimators=140, criterion='entropy')
            elif model == 'mlp':
                self.model = neural_network.MLPClassifier(activation='tanh', hidden_layer_sizes=20,
                                                          learning_rate='adaptive', learning_rate_init=0.104,
                                                          max_iter=10000, alpha=0.029, solver='adam')
            elif model == 'svm':
                self.model = svm.SVC(kernel='rbf', C=1000.0)
            else:  # svm
                self.model = svm.SVC(kernel='linear', probability=True)

            self.model.fit(X, y)

            if num_sets > 1:
                y_pred = self.model.predict(y_test)
                y_prob = self.model.predict_proba(y_test)
                print(classification_report(y_test, y_pred))

        if save_model_path is not None:
            folder = path.dirname(save_model_path)
            makedirs(folder, exist_ok=True)

            with open(save_model_path, 'wb') as f:
                pickle.dump(self.model, f)

            parameters_csv = path.join(path.dirname(save_model_path), f"{model}_parameters.csv")
            parameters = self.model.get_params()
            if not path.exists(parameters_csv):
                file = open(parameters_csv, "w")
                file.write(';'.join(param_name for param_name in parameters.keys()) + ";Score\n")
            else:
                file = open(parameters_csv, 'a')
            file.write(';'.join(str(param_value) for param_value in list(parameters.values())) + f";{str(score)}\n")
            file.close()

    def classify(self, descriptor):
        if self.model is None:
            print('Train the model before doing classifications.')
            return
        pred = self.model.predict([descriptor])
        prob = self.model.predict_proba([descriptor])

        return pred[0], round(float(np.ravel(prob)[0]), 2)

