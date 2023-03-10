# -*- coding: utf-8 -*-
"""Sentiment_Analysis_using_Deep_Learning.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1HQU2tRTVOR8TkGu6kqv9VRZJGg6N1SwA

# Sentiment Analysis

# Dicoding Indonesia - Machine Learning Terapan

# Alfendio Alif Faudisyah

# Install Library

## pyTorch
"""

# pip install torch torchvision

"""## Transformers
Lbrary yang menyediakan general-purpose architectures (BERT, GPT-2, XLM, dll) untuk NLU
"""

# pip install transformers

"""# Import Library"""

import torch

import random
import numpy as np
import pandas as pd
from tqdm import tqdm

from torch import optim
import torch.nn.functional as F

 
from transformers import BertForSequenceClassification, BertConfig, BertTokenizer
from nltk.tokenize import TweetTokenizer
 
from indonlu.utils.forward_fn import forward_sequence_classification
from indonlu.utils.metrics import document_sentiment_metrics_fn
from indonlu.utils.data_utils import DocumentSentimentDataset, DocumentSentimentDataLoader

"""# Clone

Clone akun github IndoNLU untuk menyimpan dataset pada storage session Google Colab
"""

!git clone https://github.com/indobenchmark/indonlu

"""# Definisikan fungsi umum
- set_seed : Mengatur dan menetapkan random seed.
- count_param : Menghitung jumlah parameter dalam model
- get_lr : Mengatur learning rate
- metrics_to_string : Mengonversi metriks ke dalam string

## Common functions
"""

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    
def count_param(module, trainable=False):
    if trainable:
        return sum(p.numel() for p in module.parameters() if p.requires_grad)
    else:
        return sum(p.numel() for p in module.parameters())
    
def get_lr(optimizer):
    for param_group in optimizer.param_groups:
        return param_group['lr']
 
def metrics_to_string(metric_dict):
    string_list = []
    for key, value in metric_dict.items():
        string_list.append('{}:{:.2f}'.format(key, value))
    return ' '.join(string_list)

"""# Set random seed"""

set_seed(19072021)

"""# Configuration and Load Pre-trained Model

## Load tokenizer and config
"""

tokenizer = BertTokenizer.from_pretrained('indobenchmark/indobert-base-p1')
config = BertConfig.from_pretrained('indobenchmark/indobert-base-p1')
config.num_labels = DocumentSentimentDataset.NUM_LABELS

"""## Instantiate model"""

model = BertForSequenceClassification.from_pretrained('indobenchmark/indobert-base-p1', config=config)

model

"""## Jumlah parameter"""

count_param(model)

"""# Dataset Preparation"""

train_dataset_path = '/content/indonlu/dataset/smsa_doc-sentiment-prosa/train_preprocess.tsv'
valid_dataset_path = '/content/indonlu/dataset/smsa_doc-sentiment-prosa/valid_preprocess.tsv'
test_dataset_path = '/content/indonlu/dataset/smsa_doc-sentiment-prosa/test_preprocess_masked_label.tsv'

"""## Mendefinisikan variabel kelas"""

train_dataset = DocumentSentimentDataset(train_dataset_path, tokenizer, lowercase=True)
valid_dataset = DocumentSentimentDataset(valid_dataset_path, tokenizer, lowercase=True)
test_dataset = DocumentSentimentDataset(test_dataset_path, tokenizer, lowercase=True)
 
train_loader = DocumentSentimentDataLoader(dataset=train_dataset, max_seq_len=512, batch_size=32, num_workers=16, shuffle=True)  
valid_loader = DocumentSentimentDataLoader(dataset=valid_dataset, max_seq_len=512, batch_size=32, num_workers=16, shuffle=False)  
test_loader = DocumentSentimentDataLoader(dataset=test_dataset, max_seq_len=512, batch_size=32, num_workers=16, shuffle=False)

print(train_dataset[0])

w2i, i2w = DocumentSentimentDataset.LABEL2INDEX, DocumentSentimentDataset.INDEX2LABEL
print(w2i)
print(i2w)

"""# Uji Model dengan Contoh Kalimat"""

text = 'Bahagia hatiku melihat pernikahan putri sulungku yang cantik jelita'
subwords = tokenizer.encode(text)
subwords = torch.LongTensor(subwords).view(1, -1).to(model.device)
 
logits = model(subwords)[0]
label = torch.topk(logits, k=1, dim=-1)[1].squeeze().item()
 
print(f'Text: {text} | Label : {i2w[label]} ({F.softmax(logits, dim=-1).squeeze()[label] * 100:.3f}%)')

"""# Fine Tuning and Evaluation"""

optimizer = optim.Adam(model.parameters(), lr=3e-6)
model = model.cuda()

"""# Train"""

# Train
n_epochs = 5
for epoch in range(n_epochs):
    model.train()
    torch.set_grad_enabled(True)
 
    total_train_loss = 0
    list_hyp, list_label = [], []
 
    train_pbar = tqdm(train_loader, leave=True, total=len(train_loader))
    for i, batch_data in enumerate(train_pbar):
        # Forward model
        loss, batch_hyp, batch_label = forward_sequence_classification(model, batch_data[:-1], i2w=i2w, device='cuda')
 
        # Update model
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
 
        tr_loss = loss.item()
        total_train_loss = total_train_loss + tr_loss
 
        # Calculate metrics
        list_hyp += batch_hyp
        list_label += batch_label
 
        train_pbar.set_description("(Epoch {}) TRAIN LOSS:{:.4f} LR:{:.8f}".format((epoch+1),
            total_train_loss/(i+1), get_lr(optimizer)))
 
    # Calculate train metric
    metrics = document_sentiment_metrics_fn(list_hyp, list_label)
    print("(Epoch {}) TRAIN LOSS:{:.4f} {} LR:{:.8f}".format((epoch+1),
        total_train_loss/(i+1), metrics_to_string(metrics), get_lr(optimizer)))
 
    # Evaluate on validation
    model.eval()
    torch.set_grad_enabled(False)
    
    total_loss, total_correct, total_labels = 0, 0, 0
    list_hyp, list_label = [], []
 
    pbar = tqdm(valid_loader, leave=True, total=len(valid_loader))
    for i, batch_data in enumerate(pbar):
        batch_seq = batch_data[-1]        
        loss, batch_hyp, batch_label = forward_sequence_classification(model, batch_data[:-1], i2w=i2w, device='cuda')
        
        # Calculate total loss
        valid_loss = loss.item()
        total_loss = total_loss + valid_loss
 
        # Calculate evaluation metrics
        list_hyp += batch_hyp
        list_label += batch_label
        metrics = document_sentiment_metrics_fn(list_hyp, list_label)
 
        pbar.set_description("VALID LOSS:{:.4f} {}".format(total_loss/(i+1), metrics_to_string(metrics)))
        
    metrics = document_sentiment_metrics_fn(list_hyp, list_label)
    print("(Epoch {}) VALID LOSS:{:.4f} {}".format((epoch+1),
        total_loss/(i+1), metrics_to_string(metrics)))

"""# Evaluate on test"""

# Evaluate on test
model.eval()
torch.set_grad_enabled(False)
 
total_loss, total_correct, total_labels = 0, 0, 0
list_hyp, list_label = [], []
 
pbar = tqdm(test_loader, leave=True, total=len(test_loader))
for i, batch_data in enumerate(pbar):
    _, batch_hyp, _ = forward_sequence_classification(model, batch_data[:-1], i2w=i2w, device='cuda')
    list_hyp += batch_hyp
 
# Save prediction
df = pd.DataFrame({'label':list_hyp}).reset_index()
df.to_csv('pred.txt', index=False)
 
print(df)
# Evaluate on test
model.eval()
torch.set_grad_enabled(False)
 
total_loss, total_correct, total_labels = 0, 0, 0
list_hyp, list_label = [], []
 
pbar = tqdm(test_loader, leave=True, total=len(test_loader))
for i, batch_data in enumerate(pbar):
    _, batch_hyp, _ = forward_sequence_classification(model, batch_data[:-1], i2w=i2w, device='cuda')
    list_hyp += batch_hyp
 
# Save prediction
df = pd.DataFrame({'label':list_hyp}).reset_index()
df.to_csv('pred.txt', index=False)
 
print(df)

"""# Prediction"""

text = 'Alfend memang sangat amat sungguh tampan sekali'
subwords = tokenizer.encode(text)
subwords = torch.LongTensor(subwords).view(1, -1).to(model.device)
 
logits = model(subwords)[0]
label = torch.topk(logits, k=1, dim=-1)[1].squeeze().item()
 
print(f'Text: {text} | Label : {i2w[label]} ({F.softmax(logits, dim=-1).squeeze()[label] * 100:.3f}%)')