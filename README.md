
# Improvements
## Complex features
1. Action Frequency customized to the user
2. More advanced ranking methodlogies (Generative approach)
3. Incoporate user demographic into rankings
4. Query grouping within ranker using multiple previous actions
5. Feeding the prompt custom statistics about the current query

# Auto Critique

The LLM can be fed various different metrics of the data to be able to assess the ranking; in the current implemnetation it judges the ranking of a XGBRanker, and the results are interesting. An extension would be to utilize XGBRanker and LLM judgement: create training data and utilize online RL to update the LLM and XGBRanker to give more accurate prediction.

Another use of LLM in the process would be to branch out the logic based on quailitive assement of quantitative data: Use the LLM to judge the output of the model with what it anticipated, and export cmds to retrain the model by emiting certain training data to avoid skews or overfits. Or just check specific sample data that would cause a tree model to behave that way and debug the training data. Also could decide between two models using their outputs and trigger wieght_estimation of the two models being used (a1 * ranker1 + a2 * ranker2).