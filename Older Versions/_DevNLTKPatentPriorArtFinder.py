from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics.pairwise import pairwise_distances
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
import pandas as pd
import numpy as np
import re
import math
from os import path
import nltk
from nltk.tokenize import word_tokenize
from nltk.text import TextCollection
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from gensim.models import Word2Vec
nltk.download('punkt')
nltk.download('stopwords')

class _DevNLTKPatentPriorArtFinder:

    def __init__(self):
        self.corpus = []
        self.number_of_patents_with_word = {}
        self.id_col = "PublicationNumber"
        self.txt_col = "Abstract"
        self.plain_dataframe = None
        self.dataframe = None
        self.word_count_matrix = None
        self.model_words = None
        self.model_citations = None


    def init(self, csvPath, publicationNumberColumnString='PublicationNumber', comparisonColumnString='Abstract'):
        """
        Prepares csv patents data for similarity functions by creating a pandas dataframe that can be passed to the desired function.

        - Renames publicationNumberColumnString, comparisonColumnString to 'PublicationNumber' and 'Abstract', respectivly
        - Adds a tokenized representation of the 'Abstract' columns, removing stop words, punctuation, and making all chars lowercase. Numbers are replaced with _NUM_
        - Adds a bag of words vector representing the wordcount (dense) of each document for every word in the corpus
        - Adds a vector representing the tfidf values for each document

        :param csv: Takes a csv file meant to represent a collection of patents
        :param publicationNumberColumnString: Optional, set by default to 'PublicationNumber'. The name of the column that contains the number of the patents, serves as an ID for that patent in output.
        :param comparisonColumnString: Optional, set by default to 'Abstract'. The name of the column that contains the patents' text, this is the data that is actually processed.
        :return: returns a pandas dataframe that adds relevant metadata to the patents. This metadata is later used for the similarity methods.
        """

        if csvPath is None:
            raise IOError('The passed file path was empty')
        # elif path.exists(csvPath) is False:
        # raise IOError('The passed file object does not exist')

        # Column Headers for dataframe:
        # PublicationNumber #Abstract
        # Dataframe will be created
        self.id_col = publicationNumberColumnString
        self.txt_col = comparisonColumnString

        if not isinstance(csvPath, pd.DataFrame):
            self.plain_dataframe = pd.read_csv(csvPath)
            dataframe = pd.read_csv(csvPath)
        else:
            dataframe = csvPath

        # Testing that the necessary columns exist
        if self.txt_col not in dataframe.columns:
            raise IOError('the passed csv must have a column named Abstract or pass a column name as a parameter')
        if self.id_col not in dataframe.columns:
            raise IOError('the passed csv must have a column named PublicationNumber'
                          ' or pass a column name as a parameter')


#maybe don't have seperate tokenizer, and rather just do it through the matrix.
        self._tokenize(dataframe)
        self._create_matrix(dataframe)
        self._createCorpus(dataframe)
        self._bagOfWordize(dataframe, self.corpus)
        self._TFIDFize(dataframe, self.corpus)
        self._word2vecize(dataframe)
        self.dataframe = dataframe
        return dataframe


    def _create_matrix(self, dataframe):
        global count_vectorizer
        count_vectorizer = CountVectorizer()
        tokens_list = dataframe['Tokens'].tolist()
        global tokens_string
        tokens_string = [" ".join(one_list) for one_list in tokens_list]
        global matrix
        matrix = count_vectorizer.fit_transform(tokens_string)
        dataframe_matrix = pd.DataFrame(matrix.toarray(),columns=count_vectorizer.get_feature_names())
        self.word_count_matrix = dataframe_matrix

    # Private methods for init to call
    def _tokenize(self, dataframe):
        dataframe['Tokens'] = dataframe[self.txt_col].apply(self._tokenizeText)
        dataframe['TokenizedCitations'] = dataframe['Citations'].apply(self._tokenizeCitation)


    def _tokenizeCitation(self, string):
        no_commas = string.replace(',',' ')
        tokenized = word_tokenize(no_commas)
        finished = []
        for token in tokenized:
            str = self._takeAwaySuffix(token)
            finished.append(str)
        return list(set(finished))

    def _takeAwaySuffix(self, string):
        tokens = string.split('-')
        #Should always have at least a prefix and the patent, this will take away the suffix or keep it the same
        return str(tokens[0] + '-' + tokens[1])



    # Will add column to dataframe called 'Tokens'

    def _tokenizeText(self, string):
        #prepares the string for tokenization, to lowercase, then removes punctutation, then changes numbers to _NUM_
        string = string.lower()
        string = re.sub(r"\d+\.?\d*", " _NUM_ ", string)
        string = re.sub(r'[^\w\s]', '',string)
        stop_words = set(stopwords.words("english"))
        tokenized = word_tokenize(string)
        return [word for word in tokenized if not word.lower() in stop_words]

    def _createCorpus(self, dataframe):
        self.corpus = list(self.word_count_matrix.columns.values)
        return self.corpus

    # Will add column called 'BagOfWords' to dataframe
    def _bagOfWordize(self, dataframe, corpus):
        bows = self.word_count_matrix.values.tolist() #makes a list of all the rows (so will be a list of lists)
        dataframe['BagOfWords'] = bows



    def _word2vecize(self, dataframe, original = True):
        tokens = dataframe['Tokens']
        citation_tokens = dataframe['TokenizedCitations']

        if original:
            model_words = Word2Vec(tokens)
            self.model_words = model_words
            model_citations = Word2Vec(citation_tokens,min_count=1)
            self.model_citations = model_citations
        else:
            model_words = self.model_words
            model_citations = self.model_citations


        vecs =[]

        for (tokenList, citationList) in zip(tokens, citation_tokens):
            sum_words = np.empty(50)
            sum_citations = np.empty(50)
            for word in tokenList:
                try:
                    sum_words += model_words.wv[word]
                except:
                    pass
            for citation in citationList:
                try:
                    sum_citations += model_citations.wv[citation]
                except:
                    pass
            sum = np.concatenate((sum_words,sum_citations))
            vecs.append(sum)
        dataframe['Word2Vec'] = vecs




    def word2vecTable(self, dataframe):
        vecTable = pd.DataFrame(cosine_similarity(dataframe['Word2Vec'].tolist()))
        vecTable.columns = dataframe[self.id_col].tolist()
        vecTable.index = dataframe[self.id_col].tolist()
        return vecTable


    # Zach
    def _tf_idf_scikit(self):
        #https://mmuratarat.github.io/2020-04-03/bow_model_tf_idf
        global  tfidf_vectorizer
        tfidf_vectorizer = TfidfVectorizer(use_idf=True)
        # tfidf_vectorizer_vectors = tfidf_vectorizer.fit_transform(tokens_string) #tokens_string is a global vriable from above
        tfidf_vectorizer.fit(tokens_string)
        tfidf_vectorizer_vectors =  tfidf_vectorizer.transform(tokens_string)
        tf_idf_dataframe = pd.DataFrame(tfidf_vectorizer_vectors.toarray(), columns=count_vectorizer.get_feature_names())
        return tf_idf_dataframe




    def _TFIDFize(self, dataframe, corpus):
        # adding column called 'TF-IDF'
        tf_idf_dataframe = self._tf_idf_scikit()
        tf_idfs = tf_idf_dataframe.values.tolist() #makes a list of all the rows (so will be a list of lists)
        dataframe['TF-IDF'] = tf_idfs




    def cosineSimilarity(self, patent1, patent2):
        """
        Computes the cosine similarity of 2 patents. Used in CompareNewPatent below.
        Creates a 2d array to match the input requirements of scikit's cosine func,
         but only returns the 1 cell representing the 2 inputted patents

        :param patent1: Vector representing the text of 1 patent's text
        :param patent2: Vector representing the text of a 2nd patent's text
        :return: The cosine similarity index of those 2 patents
        """

        if patent1 is None or patent2 is None:
            raise IOError("One of or both of the Patents are empty")
        elif type(patent1) is not list:
            raise IOError("Patent input must be a list")
        elif len(patent1) != len(patent2):
            raise IOError("Bag of Words must be the same length")

        v1 = np.array(patent1).reshape(1, -1)
        v2 = np.array(patent2).reshape(1, -1)
        return cosine_similarity(v1, v2)[0][0]


    def cosineTable(self, dataframe):
        """
         Takes a dataframe and returns a table with the cosine simialrity metrics of each pair
        , uses scikit-learn's cosine function.

        :param dataframe: dataframe from init
        :return: pandas table with cosine similarity (SciKit implementation) index from BOW vectors
        """
        if dataframe is None:
            raise IOError("The dataframe was empty")
        elif type(dataframe) is not pd.core.frame.DataFrame:
            raise IOError("The passed object was not a dataframe")
        elif 'BagOfWords' not in dataframe.columns:
            raise IOError('The passed dataframe must have a column named BagOfWords.'
                          ' Make sure this is the dataframe returned from init')
        for row in dataframe['BagOfWords']:
            if isinstance(row, list) is False:
                raise IOError('The contents of BagOfWords column were not all lists.')
            elif all(isinstance(entry, (int, float)) for entry in row) is False:
                raise IOError('The contents of BagOfWords column were not all lists of numbers.')

        newTable = pd.DataFrame(cosine_similarity(dataframe['BagOfWords'].tolist()))
        newTable.columns = dataframe[self.id_col].tolist()
        newTable.index = dataframe[self.id_col].tolist()

        return newTable

    def cosineTableTF(self, dataframe):
        """
         Takes a dataframe and returns a table with the cosine simialrity metrics of each pair
        , uses scikit-learn's cosine function.

        :param dataframe: dataframe from init
        :return: pandas table with cosine similarity (SciKit implementation) index from TF-IDF vectors
        """
        if dataframe is None:
            raise IOError("The dataframe was empty")
        elif type(dataframe) is not pd.core.frame.DataFrame:
            raise IOError("The passed object was not a dataframe")
        elif 'TF-IDF' not in dataframe.columns:
            raise IOError('The passed dataframe must have a column named TF-IDF.'
                          ' Make sure this is the dataframe returned from init')
        for row in dataframe['TF-IDF']:
            if isinstance(row, list) is False:
                raise IOError('The contents of TF-IDF column were not all lists.')
            elif all(isinstance(entry, (int, float)) for entry in row) is False:
                raise IOError('The contents of TF-IDF column were not all lists of numbers.')

        newTable = pd.DataFrame(cosine_similarity(dataframe['TF-IDF'].tolist()))
        newTable.columns = dataframe[self.id_col]
        newTable.index = dataframe[self.id_col]

        return newTable


    # Comparing new patent based on TF-IDF/Cosine Similarity
    # dataframe must have TF-IDF column

    def compareNewPatent(self, newComparisonText, dataframe):
        """
        Takes a new patent and the old dataframe, updates the dataframe with the new patent and any new words it adds, returns a tfidf comparison table

        :param newComparisonText: The new patent to be added to the comparison
        :param dataframe: The old dataframe (with metadata created by init)
        :return: A new pandas dataframe with similarity metrics using cosine similarity based on the tfidf vectors
        """
        if newComparisonText is None:
            raise IOError("The new String is Empty")
        elif not isinstance(newComparisonText, str):
            raise IOError("The New Compariosn Text is not a String")
        elif type(dataframe) is not pd.core.frame.DataFrame:
            raise IOError("The passed object was not a dataframe")
        elif 'BagOfWords' not in dataframe.columns:
            raise IOError('The passed dataframe must have a column named TF-IDF.'
                          ' Make sure this is the dataframe returned from init')


        new_tokens = self._tokenizeText(newComparisonText)
        new_tokens_string = [" ".join(new_tokens)]
        tfidf_vectorizer_vectors = tfidf_vectorizer.transform(new_tokens_string) #tfidf_vectorizer is a global variavble from above
        new_vector = tfidf_vectorizer_vectors.toarray().tolist()[0]

        tuples = []
        # # The following 3 lines are Ephraim's simplified implementation to replace the for loop that follows. The sorting and onwards is not replaced here.
        # new_pat_vec = [new_vector for row in dataframe['BagOfWords']] # Create a 2d list where each line is the new_vector data, length matching our dataframe
        # new_comparison = cosine_similarity(dataframe['BagOfWords'].tolist(), new_pat_vec)
        # tuples = [[name,sim] for name,sim in zip(dataframe[id_col],new_comparison[0])]

        for pn, vec in zip(dataframe[self.id_col],dataframe['TF-IDF']):  # iterates through both of these columns at same time
            similarity = self.cosineSimilarity(new_vector, vec)  # compares new TF-IDF vector to the ones in dataframe
            tuples.append([pn, similarity])  # adds to the tuples, contains the patent number and similarity

        tuples = sorted(tuples, key=lambda similarity: similarity[1],reverse=True)  # sort the tuples based off of similarity
        df = pd.DataFrame(tuples,columns=[self.id_col,'Similarity'])  # turns the sorted tuple into a pandas dataframe

        return df




    #newPatent needs to be a dataframe with an abstract, and a citations column
    def compareNewPatentW2V(self, newPatent, dataframe):
        self._tokenize(newPatent) #adds tokens of abstract and citations
        self._word2vecize(newPatent, False) #adds word2vec vectors
        new_vector = newPatent.iloc[0]['Word2Vec'].tolist()




        tuples = []

        for pn, vec in zip(dataframe[self.id_col], dataframe['Word2Vec']):
            similarity = self.cosineSimilarity(new_vector,vec)
            tuples.append([pn, similarity])

        tuples = sorted(tuples, key=lambda similarity: similarity[1],reverse=True)
        df = pd.DataFrame(tuples,columns=[self.id_col,'Similarity'])  # turns the sorted tuple into a pandas dataframe

        return df




    # adds new patents to the dataframe that we want to use. Will help us add patents that we know are similiar
    # must have same key column names (for the publication number, and abstract) as the dataframe that adding to
    def _add_patents_to_data(self, csvPath, publicationNumberColumnString='PublicationNumber',
                             comparisonColumnString='Abstract'):
        df = pd.read_csv(csvPath)
        combined_df = pd.concat([self.plain_dataframe, df], axis=0, ignore_index=True)
        new_complete_df = self.init(combined_df, publicationNumberColumnString, comparisonColumnString)
        self.dataframe = new_complete_df

        return new_complete_df

    def oldmatches(self, compFrame, docFrame):
        print("Matches: ")
        print("____________________")
        r = 0
        for index, row in compFrame.iterrows():
            n = 0
            for entry in row:
                if type(entry) is not str and entry < .99 and entry >= .6:
                    print(entry)
                    print(index)
                    print(docFrame[self.id_col][n])
                    print("col: " + str(n))
                    print("row: " + str(r))
                    print(docFrame[self.txt_col][n])
                    print(docFrame[self.txt_col][r])
                    print()
                n += 1
            r += 1
        print("____________________")

    def matches(self, compFrame, docFrame, threshold=.6):
        print("Matches: ")
        print("____________________")
        for r in range(0, len(compFrame)):
            for n in range(0, r + 1):
                entry = compFrame.iloc[n][r]
                if type(entry) is not str and entry < .99 and entry >= threshold:
                    print("val: " + str(compFrame.iloc[n][r]))
                    print(compFrame.columns[r])
                    print(compFrame.columns[n])
                    print("col: " + str(n))
                    print("row: " + str(r))
                    print(docFrame[self.txt_col][n])
                    print(docFrame[self.txt_col][r])
                    print()
        print("____________________")
