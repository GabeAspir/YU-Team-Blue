import shutil

import scipy.spatial.distance
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np
import re
import os
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from gensim.models import Word2Vec
from gensim import models
from gensim.corpora import Dictionary
from timeit import default_timer as timer
import nltk.downloader
nltk.download('stopwords')


class _DevFilesPatentPriorArtFinder:
    def __init__(self, dirPath, publicationNumberColumnString='Publication_Number', comparisonColumnString='Abstract', cit_col= "Citations", tfidf = None):
        start_time = timer()
        self.model_words = None
        self.model_citations = None
        self.dictionary = Dictionary()
        self.dirPath= os.path.normpath(dirPath)
        if dirPath is None:
            raise IOError('The passed file path was empty')
        self.id_col = publicationNumberColumnString
        self.txt_col = comparisonColumnString
        self.cit_col = cit_col
        self.old = True
        self.first = True
        self.tfidf = tfidf

        if tfidf is not False and tfidf is not True and tfidf is not None:
            raise Exception('Invalid TFIDF parameter input')


            # os.mkdir(dirPath+"/other")
            # os.mkdir(dirPath+"/w2v")
        print("Initialization complete T="+str(timer()))

    def train(self):
        # Create the folders for metadata files, and will pass should an error thown when the directory exists from a previous object
        print(os.path.join(self.dirPath,"meta"))
        try:
            shutil.rmtree(os.path.join(self.dirPath,"w2v"))
        except:
            pass
        try:
            shutil.rmtree(os.path.join(self.dirPath, "meta"))
        except:
            pass
        try:
            shutil.rmtree(os.path.join(self.dirPath, "other"))
        except:
            pass

        os.mkdir(os.path.join(self.dirPath,"w2v"))
        os.mkdir(os.path.join(self.dirPath,"other"))
        os.mkdir(os.path.join(self.dirPath,"meta"))

        # Iterates over the files in the directory twice.
        # Once to save the tokenization column to the file, and adds the file to the model's training
        # 2nd time to append the w2v encodings generated from the fully trained model to the files.
        print("Training has begun")
        self.first=True
        for entry in os.scandir(self.dirPath):
            if entry.is_file():    # To avoid entering the directories
                print("tokenizing "+ str((entry)))
                self._makeModel(entry)
        print("Tokenization Completed T="+str(timer()))
        self.tfidf_model= models.TfidfModel(dictionary=self.dictionary)
        for entry in os.scandir(self.dirPath):
            if entry.is_file():
                print("getting embedding of "+str(entry)+" T="+str(timer()))
                self._makeEmbeddings(entry)
        print("Embeddings completed"+str(timer()))
        self.model_words.save(os.path.join (self.dirPath,"other","model_words.model"))
        self.model_citations.save(os.path.join(self.dirPath,"other","model_citations.model"))
        self.dictionary.save_as_text(os.path.join(self.dirPath,"other","dict.txt"))
        self.old=False

    def is_gz_file(self, filepath):
        with open(filepath, 'rb') as test_f:
            return test_f.read(2) == b'\x1f\x8b'

    # Private methods for train to call
    def _makeModel(self,file):
        try:
            dataframe= pd.io.json.read_json(file,compression="gzip")
        except:
            dataframe= pd.io.json.read_json(file,compression="gzip",lines=True)
        #dataframe= pd.DataFrame(index=dataframe[self.id_col])
        dataframe['Tokens'] = dataframe[self.txt_col].apply(self._tokenizeText)
        dataframe['TokenizedCitations'] = dataframe['Citations'].apply(self._tokenizeCitation)
        # words = 0
        # for index,doc in dataframe.iterrows():
        #     words += len(doc["Tokens"])
        # print(str(file)+" has "+ str(words) +" word tokens")
        self.dictionary.add_documents(dataframe['Tokens'])

        print("Writing "+str(file))
        dataframe.to_json(self.get(file,"meta"), orient='records', indent=4)

        if self.first:
            self.first= False
            # TODO: This local model_words seems redundant
            model_words = Word2Vec(dataframe['Tokens'],vector_size=50)
            self.model_words = model_words
            model_citations = Word2Vec(dataframe['TokenizedCitations'], min_count=1, vector_size=50)
            self.model_citations = model_citations
        else:
            self.model_words.build_vocab(dataframe["Tokens"], update=True)
            self.model_words.train(dataframe["Tokens"], total_examples=self.model_words.corpus_count, epochs=self.model_words.epochs)
            self.model_citations.build_vocab(dataframe["TokenizedCitations"], update=True)
            self.model_citations.train(dataframe['TokenizedCitations'],total_examples=self.model_citations.corpus_count, epochs=self.model_citations.epochs)
    def _tokenizeCitation(self, string):
        no_commas = string.replace(',',' ')
        tokenized = word_tokenize(no_commas)
        finished = []
        for token in tokenized:
            str = self._removeSuffix(token)
            finished.append(str)
        return list(set(finished))

    def _removeSuffix(self, string):
        tokens = string.split('-')
        # Should always have at least a prefix and the patent, this will take away the suffix or keep it the same
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


    def _makeEmbeddings(self, file):
        try:
            dataframe= pd.io.json.read_json(self.get(file,"meta"), orient = 'records', lines=True)
        except:
            dataframe= pd.io.json.read_json(self.get(file,"meta"), orient = 'records')

        corpus = [self.dictionary.doc2bow(line) for line in dataframe['Tokens']]
        # Replaced with 1 time generation in train() between the loops
        #self.tfidf_gensim = models.TfidfModel(corpus)
        dataframe['TF-IDF'] = [self.tfidf_model[corpus[x]] for x in range(0, len(corpus))]
        dataframe.to_json(self.get(file,'meta'), orient = 'records', indent=4)
        word_vecs = []
        tfidf_vecs= []
        citations = []
        # print('make embeddings')
        # print(self.model_words.wv.most_similar('computer', topn=10))
        # print(self.model_words.wv["computer"])
        for (tokenList, citationList, tfidfList) in zip(dataframe['Tokens'], dataframe['TokenizedCitations'], dataframe["TF-IDF"]):
            sum_words = np.zeros(50)
            sum_citations = np.zeros(50)
            sum_tfidf = np.zeros(50)
            tfidfDict = dict(tfidfList)
            # Create a sum of the words in a given document to create a doc vector
            # Maintain 2 such vectors: 1 plain, and another where each word vector is multiplied by the word's tfidf weight
            for word in tokenList:
                index = self.dictionary.token2id.get(word)
                tfidfValue = tfidfDict.get(index)
                try:
                    if self.tfidf is None:
                        sum_words= np.add(sum_words ,self.model_words.wv[word])
                        sum_tfidf= np.add(sum_tfidf, tfidfValue * np.array(self.model_words.wv[word]))
                    elif self.tfidf is True:
                        sum_tfidf = np.add(sum_tfidf, tfidfValue * np.array(self.model_words.wv[word]))
                    elif self.tfidf is False:
                        sum_words = np.add(sum_words, self.model_words.wv[word])
                except: # In case the model does not have a given word, ignore it.
                    pass

            for citation in citationList:
                try:
                    sum_citations = np.add(sum_citations,self.model_citations.wv[citation])
                except:
                    pass
            citations.append(sum_citations)
            if self.tfidf is None:
                word_vecs.append(sum_words)
                tfidf_vecs.append(sum_tfidf)
            elif self.tfidf is False:
                word_vecs.append(sum_words)
            elif self.tfidf:
                tfidf_vecs.append(sum_tfidf)
        vec_frame = pd.DataFrame(dataframe[self.id_col])
        vec_frame['Citations'] = citations
        if self.tfidf is None:
            vec_frame['Word2Vec'] = word_vecs
            vec_frame['tfidf_w2v'] = tfidf_vecs
        elif self.tfidf is False:
            vec_frame['Word2Vec'] = word_vecs
        elif self.tfidf:
            vec_frame['tfidf_w2v'] = tfidf_vecs
        vec_frame.to_json(self.get(file,'w2v'), orient = 'records', indent=4)


    @staticmethod
    def get(entry, folder): # To easily access the meta-data files in parallel folders
        head, tail = os.path.split(entry.path)
        return os.path.join(head,folder,tail)

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
        # elif type(patent1) is not list:
        #     raise IOError("Patent input must be a list, not "+str(type(patent1)))
        elif len(patent1) != len(patent2):
            raise IOError("Bag of Words must be the same length")
        v1 = np.array(patent1).reshape(1, -1)
        v2 = np.array(patent2).reshape(1, -1)
        return cosine_similarity(v1, v2)[0][0]


    # Comparing new patent based on TF-IDF/Cosine Similarity
    # dataframe must have TF-IDF column
    def compareNewPatent(self, newPatentSeries, dirPath, threshold, use_tfidf=None,use_citations=True):
        dirPath = os.path.normpath(dirPath)
        newPatentSeries['Tokens'] = self._tokenizeText(string=newPatentSeries['Abstract'])
        newPatentSeries['TokenizedCitations']= self._tokenizeCitation(string=newPatentSeries['Citations'])
        if use_tfidf is not None:
            self.tfidf= use_tfidf
        if self.tfidf is None:
            self.tfidf = True
        sum_words = np.zeros(50)
        sum_citations = np.zeros(50)
        sum_tfidf = np.zeros(50)
        # print(newPatentSeries["Citations"])
        #if newPatentSeries["Citations"] == "":
        #    use_citations = False
        print("Using citations: "+str(use_citations))
        print("Using tfidf: "+ str(self.tfidf))
        if self.old:
            dictFile = os.path.join(dirPath,'other','dict.txt')
            self.dictionary = Dictionary.load_from_text(dictFile)
            #self.tfidf_gensim = models.TfidfModel(dictionary=self.dictionary)
            self.tfidf_model = models.TfidfModel(dictionary=self.dictionary)
            self.model_words= models.Word2Vec.load(os.path.join(dirPath,'other','model_words.model'))
            self.model_citations= models.Word2Vec.load(os.path.join(dirPath,'other','model_citations.model'))
            # print("comp new patent")
            # print(self.model_words.wv.most_similar('computer', topn=10))
        # print('before')
        # print(self.model_words.wv["invention"])
        # print(sum_words)

        tfidf_vector = self.tfidf_model[self.dictionary.doc2bow(newPatentSeries['Tokens'])]
        tfidfDict = dict(tfidf_vector)


        for word in newPatentSeries['Tokens']:
            index = self.dictionary.token2id.get(word)
            tfidfValue = tfidfDict.get(index)
            try:
                if self.tfidf is True:
                    sum_tfidf = np.add(sum_tfidf, tfidfValue * np.array(self.model_words.wv[word]))
                elif self.tfidf is False:
                    sum_words = np.add(sum_words, self.model_words.wv[word])
            except:
                pass
        for citation in newPatentSeries['TokenizedCitations']:
            try:
                sum_citations= np.add(sum_citations,self.model_citations.wv[citation])
            except:
                pass

        # newPatentSeries['Citations'] = sum_citations
        # if self.tfidf is True:
        #     sum_tfidf = np.concatenate((sum_tfidf, sum_citations))
        #     newPatentSeries['Word2Vec'] = sum_tfidf
        # else:
        #     sum = np.concatenate((sum_words, sum_citations))
        #     newPatentSeries['Word2Vec'] = sum

        matches = []
        for file in os.scandir(os.path.join(dirPath,'w2v')):
            if file.is_file(): # To avoid entering the emb directory
                print("reading "+str(file))
                try:
                    dataframe = pd.io.json.read_json(file, orient='records', lines=True)
                except:
                    dataframe = pd.io.json.read_json(file, orient='records')
                if use_citations:
                    if self.tfidf:
                        newvec = np.concatenate((sum_tfidf, sum_citations))
                    else:
                        newvec = np.concatenate((sum_words, sum_citations))
                else:
                    if self.tfidf:
                        newvec = sum_tfidf
                    else:
                        newvec = sum_words

                for index,doc in dataframe.iterrows():
                    # print(doc['Word2Vec'])
                    # print(newPatentSeries['Word2Vec'])
                    if use_citations:
                        if self.tfidf:
                            vec = np.concatenate((doc['tfidf_w2v'],doc["Citations"]))
                        else:
                            vec = np.concatenate((doc['Word2Vec'],doc["Citations"]))
                    else:
                       if self.tfidf:
                           vec = doc['tfidf_w2v']
                       else:
                            vec= doc['Word2Vec']
                    try:
                        similarity = 1 - scipy.spatial.distance.cosine(newvec, vec)
                    except:
                        print("Vec for doc "+doc+" @index "+str(index))
                        print(doc['Word2Vec'])
                    if similarity >= threshold:
                        matches.append((similarity,doc['publication_number']))
                        #matches.append((similarity, doc))
        matches = sorted(matches, key=lambda similarity: similarity[0], reverse=True)
        matches = pd.DataFrame(matches, columns=["similarity","Patent Number"])
        matches["Link"] = [self.get_link(number) for number in matches["Patent Number"]]
        print(str(len(matches))+" Matches found")
        return matches
        #return sorted(matches, key=lambda similarity: similarity[0], reverse=True)

    @staticmethod
    def get_link(patent_num):
        num = patent_num.replace('-','')
        return 'https://patents.google.com/patent/'+num