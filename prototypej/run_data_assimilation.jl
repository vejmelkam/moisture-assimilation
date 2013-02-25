#!julia

#
#  This is the main file for data assimilation runs.
#
#
# 1. loads up a configuration file,
# 2. obtains data from a WRF model,
# 3. reads in observations and metadata for a list of stations,
# 4. runs the moisture model and the assimilation mechanism.
#
#

using Storage



function main(args)

    # the arguments passed to the julia program do not include program name
    if length(args) != 1
        println("Usage: julia run_data_assimilation.jl cfg_file")
        exit(1)
    end

    
    cfg = evalfile(args[1])

end


main(ARGS)