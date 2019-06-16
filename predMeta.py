from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, ArgumentError
import os
from os.path import join
import traceback
import sys
import numpy as np
import pandas as pd
from keras.backend import set_image_data_format
from keras.models import load_model
import skimage
from PIL import Image
sys.path.append('./code')
from trainCNN import getPreprocess


def meanPrediction(modelPredDF, yVals=[0, 1, 2, 3]):
    """
    output the mean probability predicted by each model
    :param modelPredDF: dataframe containing the predictions
    from all models for each class (pd Dataframe)
    :param yVals: possible output classes
    :return: mean probability for each class
    """
    meanPred = pd.DataFrame(index=modelPredDF.index)
    for yi in np.unique(yVals):
        mean = modelPredDF.filter(regex='_{}'.format(yi)).mean(axis=1)
        meanPred['mean_{}'.format(yi)] = mean
    meanPred = meanPred.div(meanPred.sum(axis=1), axis=0)
    return meanPred


def preprocessImgs(xPath, newSize):
    """
    preprocess images in the directory and return data
    :param xPath: path to image directory containing .jpeg files (str)
    :param newSize: desired shape of each image array (tuple - [xRes, yRes, channels])
    :return: preprocessed image array (nImages, xRes, yRes, channels), list of image names
    """
    imgFiles = os.listdir(xPath)
    imgFiles = [f for f in imgFiles if f.endswith('.jpeg')]
    imgStack = []
    for imgFname in imgFiles:
        imgPath = os.path.join(xPath, imgFname)
        imgArr = np.array(Image.open(imgPath))
        imgArr = skimage.transform.resize(imgArr, newSize)
        imgArr = (imgArr - imgArr.min())/imgArr.max()
        imgStack.append(imgArr)
    imgStack = np.stack(imgStack, axis=0)
    imgNames = [n.split('.')[0] for n in imgFiles]  # include text before .jpeg file ending
    return imgStack, imgNames


def get_parser():
    """defines the parser for this script"""
    module_parser = ArgumentParser(
        formatter_class=ArgumentDefaultsHelpFormatter)
    module_parser.add_argument("-i", dest="xPath", type=str,
                               help="input image directory")
    module_parser.add_argument("-o", dest="outPath", type=str,
                               help="output dir path")
    module_parser.add_argument("-m", dest="modelPath",
                               type=str,
                               help="path to model directory")
    return module_parser


def main(xPath, outPath, metaPath):
    """
    takes a directory of new images and runs inference with the trained CNN
    :param xPath: path to directory of new images
    :param outPath: path to directory for predictions
    :param xRes: desired image width for preprocessing [may be changed for model] (int)
    :param yRes: desired image height for preprocessing [may be changed for model] (int)
    :param modelPath: path to .hdf5 file of trained CNN
    :return: None
    """

    """############################################################################
                        0. Preprocess Data
    ############################################################################"""
    set_image_data_format('channels_last')
    imgTypeDict = {
        0: "NORMAL",
        1: "DRUSEN",
        2: "CNV",
        3: "DME",
    }
    modelDirs = os.listdir(metaPath)
    modelDirs = [d for d in modelDirs if os.path.isdir(join(metaPath, modelDirs))]
    modelPredDict = {}
    # chose which preprocessing method to use by detecting the
    # model name in modelPath
    models = ['InceptionV3', 'VGG16', 'ResNet50', 'Xception']
    for modelName in models:
        preprocessInput = getPreprocess(modelName)
        if modelName == "VGG16":
            res = 224
        else:
            res = 299
        newSize = (res, res, 3)
        imgData, imgNames = preprocessImgs(xPath, newSize)
        imgData = preprocessInput(imgData)

        """############################################################################
                            0. load model & predict
        ############################################################################"""
        # find path to individual model
        for modelDir in modelDirs:
            if modelName in modelDir:
                break
        modelDirPath = join(metaPath,
                            modelDir,)
        modelPath = join(modelDirPath,
                         modelName+".hdf5")
        model = load_model(modelPath)
        yPred = model.predict(imgData,
                              batch_size=1,
                              verbose=1)

        # save intermediate predictions to csv
        cols = []
        for i in range(yPred.shape[1]):
            cols.append(modelName + "_{}_{}".format(imgTypeDict[i], i))
        yPredDf = pd.DataFrame(yPred,
                               columns=cols,
                               index=imgNames)
        yPredDf.to_csv(join(modelDirPath,
                            "{}_predictions.csv".format(modelName)))
        modelPredDict[modelName] = yPredDf

    # merge predictions into a single dataframe
    modelPredDF = pd.DataFrame(index=imgNames)
    for modelName in models:
        modelPredDF = pd.merge(modelPredDF,
                               modelPredDict[modelName],
                               left_index=True,
                               right_index=True)
    # calculate average probability for each class
    meanPredDF = meanPrediction(modelPredDF)
    # save dataframes to csv
    modelPredDF.to_csv(join(outPath,
                            "modelPredictions.csv"))
    meanPredDF.to_csv(join(outPath,
                            "metaClfPred_meanProba.csv"))


if __name__ == "__main__":
    parser = get_parser()
    try:
        args = parser.parse_args()
        main(args.xPath,
             args.outPath,
             args.modelPath)
        print('predMeta.py ... done!')
    except ArgumentError as arg_exception:
        traceback.print_exc()
    except Exception as exception:
        traceback.print_exc()
    sys.exit()