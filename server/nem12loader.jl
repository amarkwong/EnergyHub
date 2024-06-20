using DataFrames, CSV

# Define the headers for different record types
const _100row = ["RecordIndicator", "VersionHeader", "DateTime", "FromParticipant", "ToParticipant"]
const _200row = ["RecordIndicator", "NMI", "NMIConfiguration", "RegisterID", "NMISuffix", "MDMDataStreamIdentifier", "MeterSerialNumber", "UOM", "IntervalLength", "NextScheduledReadDate"]
const _300row = ["RecordIndicator", "IntervalDate", "QualityMethod", "ReasonCode", "ReasonDescription", "UpdateDateTime", "MSATSLoadDateTime"]
const _400row = ["RecordIndicator", "StartInterval", "EndInterval", "QualityMethod", "ReasonCode", "ReasonDescription"]

function parse_nem12(file_path::String)
    df = DataFrame()
    dfs = DataFrame[]
    _200Record = Dict{String, String}()

    open(file_path) do file
        for ln in eachline(file)
            line = split(ln, ',')

            if line[1] == "100"
                # 100 row should only have 5 columns https://aemo.com.au/-/media/files/electricity/nem/retail_and_metering/metering-procedures/2017/mdff_specification_nem12_nem13_final_v102.pdf 
                if length(line) >= 6 
                    pop!(line)
                end
                try
                    _100Record = Dict(_100row .=> line)
                catch e
                    println("Error parsing 100 row: ", e)
                end

            elseif line[1] == "200"
                if length(line) >= 11
                    pop!(line)
                end
                try
                    _200Record = Dict(_200row .=> line)
                catch e
                    println("Error parsing 200 row: ", e)
                end

            elseif line[1] == "300"
                Numbers_of_Intervals = 24 * 60 ÷ parse(Int, _200Record["IntervalLength"])
                NMISuffix = _200Record["NMISuffix"]
                NMI = _200Record["NMI"]
                QualityMethod = line[3 + Numbers_of_Intervals]
                IntervalDate = parse(Int, line[2])

                if "NMI" in names(df)
                    if last(df.NMI) != NMI || last(df.IntervalDate) != IntervalDate
                        push!(dfs, df)
                        df = DataFrame(NMI = fill(NMI, Numbers_of_Intervals),
                                       IntervalDate = fill(IntervalDate, Numbers_of_Intervals),
                                       Interval = 1:Numbers_of_Intervals)
                    end
                else
                    df = DataFrame(NMI = fill(NMI, Numbers_of_Intervals),
                                   IntervalDate = fill(IntervalDate, Numbers_of_Intervals),
                                   Interval = 1:Numbers_of_Intervals)
                end

                df[!, Symbol(NMISuffix)] = line[3:3 + Numbers_of_Intervals - 1]
                df[!, Symbol("Quality_$NMISuffix")] = fill(QualityMethod, Numbers_of_Intervals)

            elseif line[1] == "400"
                NMISuffix = _200Record["NMISuffix"]
                _400Record = Dict(_400row .=> line)
                StartInterval = parse(Int, _400Record["StartInterval"])
                EndInterval = parse(Int, _400Record["EndInterval"])
                QualityMethod = _400Record["QualityMethod"]

                for i in StartInterval:EndInterval
                    df[df.Interval .== i, Symbol("Quality_$NMISuffix")] .= QualityMethod
                end

            elseif line[1] == "500"
            elseif line[1] == "900"
            else
                println("unknown row")
            end
        end

        push!(dfs, df)
    end

    return dfs
end


# Function to fetch columns starting with a specific prefix
function get_columns_with_prefix(df::DataFrame, prefix::String)
    # Filter column names that start with the given prefix
    columns_with_prefix = filter(name -> occursin(r"^$prefix\d*$", string(name)), names(df))
    # Select and return the columns
    return select(df, columns_with_prefix)
end

file_path = "./data/NEM12.csv"
dfs = parse_nem12(file_path)


println(((dfs[1][:,"E1"]-dfs[1][:,"B1"]).^2 + (dfs[1][:,"Q1"]-dfs[1][:,"K1"]).^2).^0.5)