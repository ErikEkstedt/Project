# Modular
# without understand

echo "Modular without understand"
python eval_modular.py \
	--feature-maps 64 64 64 --render \
	--hidden=256 --update-target=300 --MAX_TIME=1200\
	--train-target-path="/home/erik/DATA/Reacher/SocialReacher_S(6,)_O40-40-3_n50000_1.h5" \
	--state-dict-path="/home/erik/DATA/Reacher/experiments/All/Coordination/checkpoints/BestDictCombi4153344_63.26.pt"\
	--state-dict-path2="/home/erik/DATA/Reacher/experiments/All/Understanding/Dict1.243e-05/run-3/checkpoints/BestUnderDict95_1.2435867166478063e-05.pt"\
	--log-dir="/home/erik/DATA/Reacher/tests/videos" \
	--record-name="modular" --record 

echo "Modular with understand"
python eval_modular.py \
	--feature-maps 64 64 64 --render \
	--hidden=256 --update-target=300 --MAX_TIME=1200\
	--train-target-path="/home/erik/DATA/Reacher/SocialReacher_S(6,)_O40-40-3_n50000_1.h5" \
	--state-dict-path="/home/erik/DATA/Reacher/experiments/All/Coordination/checkpoints/BestDictCombi4153344_63.26.pt"\
	--state-dict-path2="/home/erik/DATA/Reacher/experiments/All/Understanding/Dict1.243e-05/run-3/checkpoints/BestUnderDict95_1.2435867166478063e-05.pt"\
	--log-dir="/home/erik/DATA/Reacher/tests/videos" \
	--record-name="modular" --record --use-understand

# SemiCombine

echo "SemiModular without understand"
python eval_semicombine.py \
	--feature-maps 64 64 32 --render \
	--hidden=256 --update-target=300 --MAX_TIME=1200\
	--train-target-path="/home/erik/DATA/Reacher/SocialReacher_S(6,)_O40-40-3_n50000_1.h5" \
	--state-dict-path="/home/erik/DATA/Reacher/experiments/All/SemiCombine5M/checkpoints/BestDictCombi3948544_49.812.pt" \
	--state-dict-path2="/home/erik/DATA/Reacher/experiments/All/Understanding/Dict1.243e-05/run-3/checkpoints/BestUnderDict95_1.2435867166478063e-05.pt"\
	--log-dir="/home/erik/DATA/Reacher/tests/videos" \
	--record-name="semimodular" --record 

echo "SemiModular with understand"
python eval_semicombine.py \
	--feature-maps 64 64 32 --render \
	--hidden=256 --update-target=300 --MAX_TIME=1200\
	--train-target-path="/home/erik/DATA/Reacher/SocialReacher_S(6,)_O40-40-3_n50000_1.h5" \
	--state-dict-path="/home/erik/DATA/Reacher/experiments/All/SemiCombine5M/checkpoints/BestDictCombi3948544_49.812.pt" \
	--state-dict-path2="/home/erik/DATA/Reacher/experiments/All/Understanding/Dict1.243e-05/run-3/checkpoints/BestUnderDict95_1.2435867166478063e-05.pt"\
	--log-dir="/home/erik/DATA/Reacher/tests/videos" \
	--record-name="semimodular" --record --use-understand 

echo "Combine"
python eval_combine.py \
	--feature-maps 64 64 32 --render \
	--hidden=256 --update-target=300 --MAX_TIME=1200 \
	--train-target-path="/home/erik/DATA/Reacher/experiments/All/Understanding/Dict1.243e-05/run-3/checkpoints/BestUnderDict95_1.2435867166478063e-05.pt"\
	--state-dict-path="/home/erik/DATA/Reacher/experiments/All/Combine/checkpoints/BestDictCombi3948544_53.956.pt" \
	--log-dir="/home/erik/DATA/Reacher/tests/videos" \
	--record-name="combine"  --record 